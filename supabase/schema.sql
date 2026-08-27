-- Su Ayak İzi — hafif çok kullanıcı şeması
-- Supabase SQL Editor'de çalıştırın.

-- Roller: firma_kullanici | adaso_yonetici
create type public.app_role as enum ('firma_kullanici', 'adaso_yonetici');

create table if not exists public.firmalar (
  id uuid primary key default gen_random_uuid(),
  ad text not null,
  sektor text default '',
  lokasyon text default '',
  created_at timestamptz not null default now()
);

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  full_name text default '',
  role public.app_role not null default 'firma_kullanici',
  firma_id uuid references public.firmalar (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.raporlar (
  id uuid primary key default gen_random_uuid(),
  firma_id uuid not null references public.firmalar (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  firma_adi text,
  mavi_su double precision,
  yesil_su double precision,
  gri_su double precision,
  toplam_su double precision,
  rapor_yili text,
  payload jsonb not null default '{}'::jsonb,
  olusturma_tarihi timestamptz not null default now()
);

create index if not exists raporlar_firma_id_idx on public.raporlar (firma_id);
create index if not exists raporlar_user_id_idx on public.raporlar (user_id);
create index if not exists raporlar_olusturma_idx on public.raporlar (olusturma_tarihi desc);
create index if not exists profiles_firma_id_idx on public.profiles (firma_id);

-- Yardımcı: mevcut kullanıcının rolü / firma_id
create or replace function public.current_role()
returns public.app_role
language sql
stable
security definer
set search_path = public
as $$
  select role from public.profiles where id = auth.uid();
$$;

create or replace function public.current_firma_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select firma_id from public.profiles where id = auth.uid();
$$;

create or replace function public.is_adaso()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'adaso_yonetici'
  );
$$;

-- Yeni kullanıcı kaydı → profil (+ isteğe bağlı firma)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_firma_id uuid;
  v_firma_adi text;
  v_role public.app_role;
begin
  v_firma_adi := coalesce(new.raw_user_meta_data->>'firma_adi', '');
  v_role := coalesce((new.raw_user_meta_data->>'role')::public.app_role, 'firma_kullanici');

  if v_firma_adi <> '' then
    insert into public.firmalar (ad)
    values (v_firma_adi)
    returning id into v_firma_id;
  end if;

  insert into public.profiles (id, email, full_name, role, firma_id)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    v_role,
    v_firma_id
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

alter table public.firmalar enable row level security;
alter table public.profiles enable row level security;
alter table public.raporlar enable row level security;

-- profiles
drop policy if exists "profiles_select_own_or_adaso" on public.profiles;
create policy "profiles_select_own_or_adaso"
  on public.profiles for select
  using (id = auth.uid() or public.is_adaso());

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
  on public.profiles for update
  using (id = auth.uid())
  with check (id = auth.uid());

-- firmalar
drop policy if exists "firmalar_select" on public.firmalar;
create policy "firmalar_select"
  on public.firmalar for select
  using (id = public.current_firma_id() or public.is_adaso());

drop policy if exists "firmalar_update_member" on public.firmalar;
create policy "firmalar_update_member"
  on public.firmalar for update
  using (id = public.current_firma_id() or public.is_adaso());

-- Kayıt sonrası firma oluşturma (trigger kaçırırsa / manuel)
drop policy if exists "firmalar_insert_auth" on public.firmalar;
create policy "firmalar_insert_auth"
  on public.firmalar for insert
  with check (auth.uid() is not null);

create or replace function public.create_firma_for_me(p_ad text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
  v_existing uuid;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;
  select firma_id into v_existing from public.profiles where id = auth.uid();
  if v_existing is not null then
    return v_existing;
  end if;
  insert into public.firmalar (ad) values (coalesce(nullif(trim(p_ad), ''), 'Adsız Firma'))
  returning id into v_id;
  update public.profiles set firma_id = v_id where id = auth.uid();
  return v_id;
end;
$$;

-- raporlar
drop policy if exists "raporlar_select" on public.raporlar;
create policy "raporlar_select"
  on public.raporlar for select
  using (firma_id = public.current_firma_id() or public.is_adaso());

drop policy if exists "raporlar_insert" on public.raporlar;
create policy "raporlar_insert"
  on public.raporlar for insert
  with check (
    user_id = auth.uid()
    and firma_id = public.current_firma_id()
  );

drop policy if exists "raporlar_delete" on public.raporlar;
create policy "raporlar_delete"
  on public.raporlar for delete
  using (
    (firma_id = public.current_firma_id() and user_id = auth.uid())
    or public.is_adaso()
  );

-- Storage bucket (SQL ile; yoksa Dashboard'dan oluşturun)
insert into storage.buckets (id, name, public)
values ('kanit', 'kanit', false)
on conflict (id) do nothing;

drop policy if exists "kanit_select" on storage.objects;
create policy "kanit_select"
  on storage.objects for select
  using (
    bucket_id = 'kanit'
    and (
      public.is_adaso()
      or (storage.foldername(name))[1] = public.current_firma_id()::text
    )
  );

drop policy if exists "kanit_insert" on storage.objects;
create policy "kanit_insert"
  on storage.objects for insert
  with check (
    bucket_id = 'kanit'
    and (storage.foldername(name))[1] = public.current_firma_id()::text
  );

drop policy if exists "kanit_delete" on storage.objects;
create policy "kanit_delete"
  on storage.objects for delete
  using (
    bucket_id = 'kanit'
    and (
      public.is_adaso()
      or (storage.foldername(name))[1] = public.current_firma_id()::text
    )
  );

-- ADASO yöneticisi atamak için (örnek — kendi user id'nizle çalıştırın):
-- update public.profiles set role = 'adaso_yonetici' where email = 'yonetici@adaso.org.tr';
