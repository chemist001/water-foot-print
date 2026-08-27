"""Giriş / kayıt ekranı (Supabase Auth) — kurumsal oturum yüzeyi."""

from __future__ import annotations

import base64
import io
from pathlib import Path

import streamlit as st
from PIL import Image

from services import activation, auth

_LOGO = Path(__file__).resolve().parent.parent / "logos" / "adaso_logo.png"


def _login_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        .stApp {
            background:
                radial-gradient(ellipse 80% 50% at 10% -10%, rgba(13,115,119,0.14), transparent 55%),
                radial-gradient(ellipse 60% 40% at 95% 5%, rgba(46,134,171,0.12), transparent 50%),
                linear-gradient(165deg, #E4ECF2 0%, #F2F6F9 45%, #E8F0F2 100%) !important;
        }
        .block-container {
            padding-top: 1.75rem !important;
            padding-bottom: 3rem !important;
            max-width: 960px !important;
        }
        .login-brand {
            text-align: center;
            margin: 0 auto 1.5rem auto;
            max-width: 420px;
        }
        .login-brand img {
            display: block;
            margin: 0 auto 1.1rem auto;
            width: 168px;
            max-width: 70%;
            height: auto;
            object-fit: contain;
            background: #fff;
            padding: 14px 16px;
            border-radius: 14px;
            border: 1px solid #E2E8EF;
            box-shadow: 0 4px 18px rgba(11, 31, 51, 0.06);
        }
        .login-brand .org {
            margin: 0 0 0.35rem 0;
            font-size: 0.78rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: #5A6B7A;
            font-weight: 600;
        }
        .login-brand .app {
            margin: 0;
            font-family: 'DM Sans', sans-serif;
            font-size: 1.45rem;
            font-weight: 600;
            color: #0B1F33;
            line-height: 1.25;
        }
        div[data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 0.3rem;
            background: #EEF3F7;
            padding: 0.28rem;
            border-radius: 10px;
            margin-bottom: 0.85rem;
            border: 1px solid #D8E0E8;
        }
        div[data-testid="stTabs"] [data-baseweb="tab"] {
            border-radius: 8px !important;
            padding: 0.5rem 1.1rem !important;
            font-weight: 500;
            color: #5A6B7A !important;
        }
        div[data-testid="stTabs"] [aria-selected="true"] {
            background: #fff !important;
            color: #0B1F33 !important;
            box-shadow: 0 1px 3px rgba(11,31,51,0.08);
        }
        div[data-testid="stForm"] {
            border: 1px solid #D8E0E8 !important;
            border-radius: 14px !important;
            padding: 1.25rem 1.35rem 1.1rem !important;
            background: #fff !important;
            box-shadow: 0 8px 28px rgba(11, 31, 51, 0.05);
        }
        .login-local {
            margin-top: 1.35rem;
            padding-top: 1rem;
            border-top: 1px solid #E4EAF0;
            text-align: center;
        }
        .login-local p {
            color: #7A8B99;
            font-size: 0.8rem;
            margin: 0 0 0.55rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _logo_data_uri(path: Path) -> str | None:
    """Logoyu kırpılmadan göstermek için beyaz kenar payı ekler."""
    if not path.exists():
        return None
    try:
        img = Image.open(path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        # Kenar payı — alt yazı ve kırmızı kutu kenarları kesilmesin
        pad_x, pad_y = 28, 32
        w, h = img.size
        canvas = Image.new("RGB", (w + pad_x * 2, h + pad_y * 2), (255, 255, 255))
        if img.mode == "RGBA":
            canvas.paste(img, (pad_x, pad_y), img)
        else:
            canvas.paste(img.convert("RGB"), (pad_x, pad_y))
        buf = io.BytesIO()
        canvas.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def _render_brand() -> None:
    uri = _logo_data_uri(_LOGO)
    if uri:
        img_html = f'<img src="{uri}" alt="ADASO — Adana Sanayi Odası" />'
    else:
        img_html = ""
    st.markdown(
        f"""
        <div class="login-brand">
          {img_html}
          <p class="org">Adana Sanayi Odası</p>
          <p class="app">Kurumsal Su Ayak İzi</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login() -> None:
    _login_styles()

    _, center, _ = st.columns([0.85, 1.3, 0.85])
    with center:
        _render_brand()

        st.markdown(
            """
            <div style="margin:0 0 1.4rem 0;padding:1.2rem 1.3rem;border-radius:14px;
                        background:linear-gradient(135deg,rgba(13,115,119,0.09),rgba(46,134,171,0.07));
                        border:1px solid #D5DEE7;">
              <div style="font-size:0.7rem;letter-spacing:0.1em;text-transform:uppercase;
                          color:#5A6B7A;font-weight:600;margin-bottom:0.4rem;text-align:center;">
                Güvenli oturum
              </div>
              <div style="color:#3D4F5F;font-size:0.92rem;line-height:1.55;text-align:center;">
                Firma hesabınızla giriş yapın. Raporlar ve fatura kanıtları firmanıza özel tutulur;
                ADASO yöneticileri tüm tesisleri izleyebilir.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not auth.cloud_configured():
            st.warning(
                "Bulut yapılandırması eksik. `.streamlit/secrets.toml` içine "
                "SUPABASE_URL ve SUPABASE_KEY ekleyin."
            )
            if st.button("Demo olarak dene", type="primary", use_container_width=True):
                from services.demo import enter_demo

                enter_demo()
                st.rerun()
            return

        pending = activation.pending()
        if pending:
            _render_activation(pending)
            return

        tab_giris, tab_kayit = st.tabs(["Giriş yap", "Yeni kayıt"])

        with tab_giris:
            with st.form("login_form"):
                email = st.text_input("E-posta", placeholder="ornek@firma.com")
                password = st.text_input("Şifre", type="password", placeholder="••••••••")
                submitted = st.form_submit_button(
                    "Giriş yap", type="primary", use_container_width=True
                )
            if submitted:
                ok, msg = auth.login(email, password)
                if ok:
                    st.rerun()
                else:
                    st.error(msg)

        with tab_kayit:
            st.caption("Hesap oluşturmak için bilgilerinizi girin; ardından aktivasyon kodunu onaylayın.")
            with st.form("register_form"):
                full_name = st.text_input("Ad soyad", placeholder="Yetkili adı")
                firma_adi = st.text_input(
                    "Firma / tesis adı", placeholder="Örn. ABC Sanayi A.Ş."
                )
                email = st.text_input(
                    "E-posta", key="reg_email", placeholder="ornek@firma.com"
                )
                pw1, pw2 = st.columns(2)
                with pw1:
                    password = st.text_input(
                        "Şifre (min. 6)",
                        type="password",
                        key="reg_pw",
                        placeholder="••••••••",
                    )
                with pw2:
                    password2 = st.text_input(
                        "Şifre tekrar",
                        type="password",
                        key="reg_pw2",
                        placeholder="••••••••",
                    )
                submitted = st.form_submit_button(
                    "Devam et", type="primary", use_container_width=True
                )
            if submitted:
                if password != password2:
                    st.error("Şifreler eşleşmiyor.")
                else:
                    ok, msg = activation.start_registration(
                        email,
                        password,
                        full_name=full_name,
                        firma_adi=firma_adi,
                    )
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown(
            '<div class="login-local"><p>Hesabınız yoksa uygulamayı kısıtlı deneyin</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Demo olarak dene (kayıtsız)", use_container_width=True):
            from services.demo import enter_demo

            enter_demo()
            st.rerun()


def _render_activation(pending: dict) -> None:
    # Eski "Supabase mail bekle" oturumunu ekran koduna çevir
    if pending.get("mode") == "supabase":
        activation.resend_code()
        st.rerun()

    display_code = pending.get("display_code")
    mailed = bool(pending.get("mailed"))

    st.markdown(
        """
        <div style="margin:0 0 1rem 0;text-align:center;">
          <div style="font-family:DM Sans,sans-serif;font-size:1.2rem;font-weight:600;
                      color:#0B1F33;margin-bottom:0.35rem;">Aktivasyon</div>
          <div style="color:#5A6B7A;font-size:0.9rem;">6 haneli kodu girin</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if display_code and not mailed:
        st.markdown(
            f"""
            <div style="text-align:center;margin:0 0 1rem 0;">
              <div style="display:inline-block;background:#F1F7F8;border:1px solid #C5DCE0;
                          border-radius:12px;padding:14px 28px;font-size:28px;letter-spacing:0.35em;
                          font-weight:700;color:#0B1F33;font-family:Consolas,Monaco,monospace;">
                {display_code}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif mailed:
        st.caption("Kod e-posta adresinize gönderildi.")

    with st.form("activation_form"):
        code = st.text_input("Kod", max_chars=6, placeholder="••••••")
        verified = st.form_submit_button(
            "Hesabı etkinleştir", type="primary", use_container_width=True
        )
    if verified:
        ok, msg = activation.verify_and_register(code)
        if ok:
            st.rerun()
        else:
            st.error(msg)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yeni kod", use_container_width=True):
            ok, msg = activation.resend_code()
            if ok:
                st.rerun()
            else:
                st.error(msg)
    with c2:
        if st.button("İptal", use_container_width=True):
            activation.clear_pending()
            st.rerun()
