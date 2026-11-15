# Despliegue en Streamlit Cloud con inicio de sesión y base de datos

LicitaPYME guarda empresas, oportunidades e historial en una base de datos. En tu laptop usa
SQLite (`data/licitapyme.db`). En la nube necesita **PostgreSQL** (Supabase) porque el disco de
Streamlit Cloud se borra cada vez que la app se reinicia.

Son tres cuentas gratuitas: **Supabase** (base de datos), **Google Cloud** (inicio de sesión) y
**Streamlit Community Cloud** (publicación). Ninguna clave va en el código: todas van en los
*Secrets* de Streamlit.

---

## 1. Base de datos en Supabase (~5 min)

1. Entra a <https://supabase.com>, crea una cuenta y un **New project**.
   - Región: **South America (São Paulo)**, la más cercana a Perú.
   - Guarda la **contraseña de la base de datos** en un lugar seguro.
2. Cuando el proyecto esté listo: botón **Connect** (arriba) → pestaña **Connection string**.
3. Copia la URI del **Session pooler** (funciona en redes IPv4, como Streamlit Cloud). Se ve así:
   ```
   postgresql://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
   ```
   Reemplaza `[YOUR-PASSWORD]` por tu contraseña. Esta es tu `DATABASE_URL`.

La app crea sus tablas sola la primera vez que se conecta.

## 2. Inicio de sesión con Google (~10 min)

1. Entra a <https://console.cloud.google.com> y crea un proyecto nuevo, por ejemplo `licitapyme`.
2. **APIs y servicios → Pantalla de consentimiento de OAuth** (o *Google Auth Platform → Branding*):
   - Tipo de usuario: **Externo**. Nombre de la app: LicitaPYME. Correo de asistencia: el tuyo.
   - En *Público / Audience*, mientras esté en modo de prueba agrega como **usuarios de prueba** los
     correos que van a ingresar (el tuyo y el del profesor), o publica la app.
3. **Credenciales → Crear credenciales → ID de cliente de OAuth**:
   - Tipo: **Aplicación web**.
   - **URI de redireccionamiento autorizados**: agrega
     `https://TU-APP.streamlit.app/oauth2callback` (la URL exacta la tendrás en el paso 3; puedes
     volver a editarla) y, para probar en tu laptop, `http://localhost:8501/oauth2callback`.
4. Copia el **ID de cliente** y el **Secreto del cliente**.

## 3. Publicar en Streamlit Community Cloud (~5 min)

1. Entra a <https://share.streamlit.io> con tu cuenta de GitHub → **Create app** → *Deploy a public app from GitHub*.
2. Repositorio: `licitapyme`, rama `main`, archivo principal: **`app/app.py`**.
   Elige una URL (por ejemplo `licitapyme.streamlit.app`).
3. En **Advanced settings**: Python **3.12** y pega los *Secrets* (plantilla abajo).
4. **Deploy**. Si cambiaste la URL, actualiza la URI de redirección en Google (paso 2.3).

### Plantilla de Secrets

```toml
DEEPSEEK_API_KEY = "sk-..."
DATABASE_URL = "postgresql://postgres.xxxx:TU_CONTRASEÑA@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"

[auth]
redirect_uri = "https://TU-APP.streamlit.app/oauth2callback"
cookie_secret = "una-cadena-larga-y-aleatoria-de-al-menos-32-caracteres"
client_id = "xxxxxxxx.apps.googleusercontent.com"
client_secret = "GOCSPX-..."
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

`cookie_secret` es cualquier texto largo y aleatorio que inventes (firma la cookie de sesión).

## Cómo se comporta la app según la configuración

| Configuración | Identidad | Dónde se guardan los datos |
|---|---|---|
| Sin `[auth]` ni `DATABASE_URL` (tu laptop) | Usuario `local` | `data/licitapyme.db` |
| Con `DATABASE_URL`, sin `[auth]` | Usuario `local` | PostgreSQL |
| Con `[auth]` y `DATABASE_URL` (nube) | Correo de Google | PostgreSQL |
| Botón "Explorar con una empresa de ejemplo" | Usuario demo temporal | La misma base, separado del resto |

## Probar en tu laptop con inicio de sesión (opcional)

Crea `.streamlit/secrets.toml` (está en `.gitignore`) con la misma plantilla, usando
`redirect_uri = "http://localhost:8501/oauth2callback"`, y corre desde la carpeta del repo:

```bash
streamlit run app/app.py
```
