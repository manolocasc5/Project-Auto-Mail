# Automatización Inteligente de Correos con FastAPI, Make.com y LangChain/Google Gemini
## 🚀 Resumen del Proyecto
Este proyecto implementa un sistema de automatización inteligente para la gestión de correos electrónicos. Utiliza Make.com para la orquestación, una API de FastAPI como cerebro lógico para la clasificación y generación de respuestas, y Google Gemini como modelo de inteligencia artificial. El objetivo es clasificar automáticamente los correos entrantes y, para ciertas categorías, generar borradores de respuesta, liberando tiempo y mejorando la eficiencia en la gestión de la bandeja de entrada.

![image](https://github.com/user-attachments/assets/a1b41822-ff4c-4e77-be81-dcdac8c3a5fa)


## ✨ Características Principales
Clasificación Automática: Los correos se clasifican en categorías predefinidas (Soporte Técnico, Ventas, Facturación, General, Devoluciones, Otro).

Generación de Respuestas (Borradores): Para correos clasificados en categorías específicas (ej. "Soporte Técnico"), se genera un borrador de respuesta automático.

Notificaciones Inteligentes: Los correos que requieren atención manual son notificados al usuario con un enlace directo al correo original en Gmail.

Integración Fluida: Conexión y flujo de datos entre Gmail, Make.com, tu API personalizada de FastAPI y Google Gemini.

## 🛠️ Herramientas y Tecnologías Utilizadas
Este proyecto integra varias herramientas y librerías clave:

### Componentes Principales
Python 3.9+: Lenguaje de programación principal para la lógica de la API.

FastAPI: Framework web de Python para construir la API.

Make.com (anteriormente Integromat): Plataforma de automatización no-code/low-code para orquestar el flujo de trabajo (leer correos, llamar a la API, enviar respuestas/notificaciones).

Google Gemini (vía Google AI Studio): Modelo de lenguaje grande (LLM) de Google utilizado para la clasificación y generación de texto.

Ngrok: Herramienta para crear un túnel seguro desde tu máquina local a internet, exponiendo tu API de FastAPI para que Make.com pueda acceder a ella.

### Librerías Python
Asegúrate de instalar todas estas librerías en tu entorno Python. Puedes hacerlo con pip:

- fastapi==0.111.0
- uvicorn==0.30.1
- python-dotenv==1.0.0
- beautifulsoup4==4.12.3
- langchain-google-genai==1.0.0
- langchain-core==0.2.14

#### Cómo utilizar requirements.txt

Para instalar todas las dependencias del proyecto, asegúrate de tener Python y pip instalados. Luego, abre tu terminal, navega hasta el directorio raíz de tu proyecto (donde se encuentra el archivo requirements.txt) y ejecuta el siguiente comando:

Bash

pip install -r requirements.txt
Esto instalará automáticamente todas las librerías con las versiones exactas especificadas, asegurando un entorno de desarrollo consistente.


uvicorn: Servidor ASGI para ejecutar la aplicación FastAPI.

python-dotenv: Para cargar variables de entorno desde un archivo .env.

beautifulsoup4 (bs4): Para parsear y limpiar contenido HTML de los correos.

langchain-google-genai: Integración de LangChain con los modelos Gemini de Google.

langchain-core: Componentes base de LangChain para la construcción de cadenas de procesamiento de lenguaje.

json (built-in): Usado internamente en la API para manejar JSON.

re (built-in): Para expresiones regulares en el procesamiento del cuerpo del correo.

## ⚙️ Configuración del Entorno y Despliegue
Sigue estos pasos para poner en marcha el proyecto desde cero.

### 1. Configuración de Google Gemini API Key
Ve a Google AI Studio o a la Consola de Google Cloud para generar una API Key para Google Gemini.

Crea un archivo llamado .env en la raíz de tu proyecto de FastAPI (en la misma carpeta que main.py).

Añade tu API Key a este archivo:

GOOGLE_API_KEY="TU_API_KEY_AQUI"
¡Importante! Nunca compartas este archivo ni lo subas a un repositorio público (GitHub). .env ya debería estar en tu .gitignore.

### 2. Desarrollo y Configuración de la API de FastAPI
El código de tu API se encuentra en main.py. Aquí se definen los endpoints para clasificar y generar respuestas.

Guarda el código de tu API (el que hemos desarrollado y depurado juntos) en un archivo llamado main.py.

Ejecuta tu API de FastAPI desde la terminal en la carpeta de tu proyecto:

Bash

uvicorn main:app --reload
Esto iniciará tu API, generalmente en http://127.0.0.1:8000 (localhost en el puerto 8000).

### 3. Exposición de la API con Ngrok
Dado que Make.com necesita acceder a tu API a través de una URL pública, usaremos Ngrok.

Descarga Ngrok desde ngrok.com/download (asegúrate de iniciar sesión y obtener tu authtoken).

Descomprime ngrok.exe en una carpeta fácil de acceder (ej., C:\ngrok).

Abre el Símbolo del Sistema (CMD) o PowerShell y navega a esa carpeta (cd C:\ngrok).

Autentica Ngrok con tu authtoken (solo una vez):

Bash

ngrok authtoken <tu_authtoken_aqui>
Con tu API de FastAPI ejecutándose, inicia el túnel Ngrok en el puerto 8000:

Bash

ngrok http 8000
Ngrok te proporcionará una URL https://...ngrok-free.app. Copia esta URL, ya que la necesitarás para configurar Make.com. Esta URL cambiará cada vez que reinicies Ngrok.

### 4. Configuración del Escenario en Make.com
Aquí se orquesta todo el flujo de trabajo.

#### Crea un nuevo Escenario en Make.com.

##### Módulo 1: Gmail - Watch Emails

Función: Inicia el escenario al detectar nuevos correos en tu bandeja de entrada.

Configuración: Conecta tu cuenta de Gmail. Decide la carpeta a monitorizar (ej., "Inbox") y la frecuencia.

##### Módulo 2: HTTP - Make a request (Clasificación)

Función: Envía los datos del correo a tu API de FastAPI para su clasificación.

Método: POST

URL: https://TU_URL_NGROK.ngrok-free.app/classify_email/ (¡reemplaza TU_URL_NGROK con la que obtuviste de Ngrok!)

Headers: Content-Type: application/json

Body Type: Raw, Content Type: JSON (application/json)

Request Content:

JSON

{
  "subject": "{{1.Subject}}",
  "body": "{{1.HTML content}}"
}
Nota: Aunque el historial de Make.com pueda mostrar esto de forma incorrecta, tu API de FastAPI está configurada para extraer subject y body robustamente del raw_body.

##### Módulo 3: Router

Función: Bifurca el flujo del escenario basándose en la categoría clasificada.

Conexión: Colócalo después del Módulo 2.

Ruta A: Responder Automáticamente (para, ej., "Soporte Técnico")

Filtro: En la línea que sale del Router.

Condición: {{2.Data.category}} Equal to "Soporte Técnico" (usa la categoría exacta que tu API devuelve).

Siguiente Módulo: HTTP - Make a request (Generar Respuesta)

Función: Llama a tu API para generar un borrador de respuesta.

Método: POST

URL: https://TU_URL_NGROK.ngrok-free.app/generate_response/

Headers: Content-Type: application/json

Body Type: Raw, Content Type: JSON (application/json)

Request Content:

JSON

{
  "subject": "{{1.Subject}}",
  "body": "{{1.HTML content}}",
  "category": "{{2.Data.category}}"
}

##### Módulo 4: HTTP - Make a request (Generar Respuesta)

Función: Llama a tu API para generar un borrador de respuesta.

Método: POST

URL: https://TU_URL_NGROK.ngrok-free.app/generate_response/

Headers: Content-Type: application/json

Body Type: Raw, Content Type: JSON (application/json)

Request Content:

JSON

{
  "subject": "{{1.Subject}}",
  "body": "{{1.HTML content}}",
  "category": "{{2.Data.category}}"
}

##### Módulo 5: Gmail - Send an Email

Función: Envía el borrador de respuesta.

To: {{1.Sender.Address}} (¡Usa tu propio email para pruebas iniciales!)

Subject: Re: {{1.Subject}}

Content: {{Resultado_del_módulo_anterior.Data.response_text}} (verifica que la variable sea la correcta del Módulo HTTP de generación de respuesta).

Ruta B: Requerir Atención (para otras categorías)

Filtro: En otra línea que sale del Router.

Condición: {{2.Data.category}} Not equal to "Soporte Técnico" (o define las categorías específicas que requieran atención).

### Módulo 6: Gmail - Send an Email (Notificación)

Función: Te envía una notificación a ti o a tu equipo.

To: Tu dirección de correo electrónico (o la de tu equipo).

Subject: ¡Alerta! Nuevo correo para revisar: {{1.Subject}}

Content:

¡Nuevo correo que requiere tu atención!

De: {{1.Sender.Address}}
Asunto: {{1.Subject}}
Categoría: {{2.Data.category}}

Puedes ver el correo aquí: {{1.Message Link}}

### 5. Pruebas y Depuración
Activa tu escenario en Make.com.

Envía correos de prueba con diferentes asuntos y cuerpos (ej., "Necesito soporte", "Comprar producto X", "Factura errónea").

Monitoriza el historial de ejecución en Make.com para ver el flujo de datos y los errores.

Revisa la consola de tu API de FastAPI para ver los mensajes DEBUG y cualquier error detallado que tu API capture.

Ajusta los prompts de tus cadenas de LangChain en main.py para mejorar la precisión de la clasificación o la calidad de las respuestas si es necesario.

## 👨‍💻 Desarrollado por:
                                        - Mahalia Yánez Monzón
                                        - Manuel Castillo Casañas

## 📄 Licencia
Este proyecto está distribuido bajo la licencia GNU General Public License v3.0 (GPLv3). Consulta el archivo LICENSE para más detalles.
