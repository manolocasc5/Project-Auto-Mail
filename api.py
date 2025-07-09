import os
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from bs4 import BeautifulSoup # ¡Importa BeautifulSoup!

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Carga las variables de entorno desde el archivo .env
load_dotenv()

# Inicialización de FastAPI
app = FastAPI(
    title="Email Classification and Response API",
    description="API para clasificar correos electrónicos y generar respuestas usando Google Gemini.",
    version="1.0.0",
)

# Configuración de Google Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY)

# 1. Definición de Pydantic Models
class EmailInput(BaseModel):
    subject: str
    body: str

class ResponseInput(BaseModel):
    subject: str
    body: str # También podría ser HTML aquí si lo usas para generar respuesta
    category: str

class CategoryOutput(BaseModel):
    category: str

class ResponseOutput(BaseModel):
    response_text: str

# 2. Plantilla para la clasificación
classification_prompt = ChatPromptTemplate.from_messages([
    ("system", """Eres un asistente de IA especializado en clasificar correos electrónicos.
    Tu tarea es clasificar el siguiente correo electrónico en una de las siguientes categorías predefinidas:
    - Soporte Técnico
    - Ventas
    - Facturación
    - General
    - Devoluciones

    Responde ÚNICAMENTE con el nombre de la categoría. No añadas explicaciones, puntos, comas ni ningún otro texto."""),
    ("human", "Asunto: {subject}\n\nCuerpo: {body}")
])

# 3. Cadena de clasificación
classification_chain = classification_prompt | llm | StrOutputParser()

# 4. Plantilla para la generación de respuesta
response_generation_prompt = ChatPromptTemplate.from_messages([
    ("system", """Eres un asistente de IA amable y servicial especializado en generar borradores de respuesta a correos electrónicos.
    Tu objetivo es crear una respuesta profesional y educada, adaptada a la categoría del correo.
    Asegúrate de que la respuesta sea concisa, clara y directa.
    No incluyas saludos ni despedidas genéricas ("Estimado", "Atentamente").
    Crea solo el cuerpo del mensaje."""),
    ("human", "Asunto del correo original: {subject}\n\nCuerpo del correo original: {body}\n\nCategoría: {category}")
])

# 5. Cadena de generación de respuesta
response_generation_chain = response_generation_prompt | llm | StrOutputParser()

# --- NUEVA FUNCIÓN PARA LIMPIAR HTML ---
def clean_html_content(html_content: str) -> str:
    """
    Limpia un string HTML, extrayendo solo el texto legible.
    """
    if not html_content:
        return ""
    # BeautifulSoup es excelente para esto
    soup = BeautifulSoup(html_content, 'html.parser')
    # get_text() extrae todo el texto, y puedes definir el separador
    # strip=True quita espacios en blanco al principio y al final
    return soup.get_text(separator=' ', strip=True)

# 6. Definición de los Endpoints de la API

@app.post("/classify_email/", summary="Clasifica un correo electrónico", response_description="Categoría del correo clasificado", response_model=CategoryOutput)
async def classify_email_endpoint(email: EmailInput):
    """
    Recibe el asunto y el cuerpo de un correo electrónico y lo clasifica
    en una categoría predefinida utilizando Google Gemini.
    """
    try:
        # ¡Limpia el HTML del cuerpo antes de pasarlo al LLM!
        cleaned_body = clean_html_content(email.body)
        category = await classification_chain.ainvoke({"subject": email.subject, "body": cleaned_body})
        return {"category": category.strip()}
    except Exception as e:
        # En caso de error, devuelve un detalle del mismo
        return {"error": f"Error al clasificar el correo: {e}"}, 500

@app.post("/generate_response/", summary="Genera una respuesta para un correo", response_description="Texto de la respuesta generada", response_model=ResponseOutput)
async def generate_response_endpoint(response_data: ResponseInput):
    """
    Genera un borrador de respuesta para un correo electrónico
    basado en su contenido y la categoría previamente clasificada.
    """
    try:
        # ¡Limpia el HTML también para la generación de respuesta si el cuerpo original es HTML!
        cleaned_body = clean_html_content(response_data.body)
        response_text = await response_generation_chain.ainvoke({
            "subject": response_data.subject,
            "body": cleaned_body,
            "category": response_data.category
        })
        return {"response_text": response_text.strip()}
    except Exception as e:
        return {"error": f"Error al generar la respuesta: {e}"}, 500

# Endpoint de prueba para verificar que la API está funcionando
@app.get("/")
async def read_root():
    return {"message": "API de automatización de correo con LangChain y Gemini funcionando!"}
