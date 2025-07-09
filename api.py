import os
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import json # Importa el módulo json para parsing manual
import re   # Importa el módulo re para expresiones regulares

# Carga las variables de entorno
load_dotenv()

app = FastAPI(
    title="Email Classification and Response API",
    description="API para clasificar correos electrónicos y generar respuestas usando Google Gemini.",
    version="1.0.0",
)

# Configuración de Google Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY) # Usando el modelo que funciona

# Modelos Pydantic (los mantenemos para validación si el JSON llega bien)
class EmailInput(BaseModel):
    subject: str
    body: str

class ResponseInput(BaseModel):
    subject: str
    body: str
    category: str

class CategoryOutput(BaseModel):
    category: str

class ResponseOutput(BaseModel):
    response_text: str

# Plantillas y Cadenas (iguales)
classification_prompt = ChatPromptTemplate.from_messages([
    ("system", """Eres un asistente de IA especializado en clasificar correos electrónicos.
    Tu tarea es clasificar el siguiente correo electrónico en una de las siguientes categorías predefinidas:
    - Soporte Técnico
    - Ventas
    - Facturación
    - General
    - Devoluciones
    - Otro (si no encaja en ninguna categoría anterior)

    Responde ÚNICAMENTE con el nombre de la categoría. No añadas explicaciones, puntos, comas ni ningún otro texto."""),
    ("human", "Asunto: {subject}\n\nCuerpo: {body}")
])
classification_chain = classification_prompt | llm | StrOutputParser()

response_generation_prompt = ChatPromptTemplate.from_messages([
    ("system", """Eres un asistente de IA amable y servicial especializado en generar borradores de respuesta a correos electrónicos.
    Tu objetivo es crear una respuesta profesional y educada, adaptada a la categoría del correo.
    Asegúrate de que la respuesta sea concisa, clara y directa.
    No incluyas saludos ni despedidas genéricas ("Estimado", "Atentamente").
    Crea solo el cuerpo del mensaje."""),
    ("human", "Asunto del correo original: {subject}\n\nCuerpo del correo original: {body}\n\nCategoría: {category}")
])
response_generation_chain = response_generation_prompt | llm | StrOutputParser()

# Función para limpiar HTML (igual)
def clean_html_content(html_content: str) -> str:
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ', strip=True)

# --- NUEVOS ENDPOINTS ADAPTADOS PARA MANEJAR ENTRADA POTENCIALMENTE MALFORMADA ---

@app.post("/classify_email/", summary="Clasifica un correo electrónico", response_description="Categoría del correo clasificado", response_model=CategoryOutput)
async def classify_email_endpoint(request: Request):
    """
    Recibe el asunto y el cuerpo de un correo electrónico y lo clasifica
    en una categoría predefinida utilizando Google Gemini.
    """
    try:
        raw_body_str = (await request.body()).decode('utf-8')
        print(f"DEBUG: Raw body received: {raw_body_str[:500]}...") # Imprime los primeros 500 caracteres para depuración

        # Intentar extraer subject y body manualmente si el JSON está malformado
        # Usamos expresiones regulares para una extracción más robusta
        subject_match = re.search(r'"subject":\s*"(.*?)(?<!\\)"', raw_body_str)
        body_match = re.search(r'"body":\s*"(.*?)(?<!\\)"', raw_body_str, re.DOTALL) # re.DOTALL para que . coincida con saltos de línea

        extracted_subject = subject_match.group(1) if subject_match else ""
        extracted_body = body_match.group(1) if body_match else ""

        # Si el body o subject están vacíos, y el raw_body sugiere un problema de comillas no escapadas,
        # intentamos un parche más agresivo para el body.
        if not extracted_body and 'dir="' in raw_body_str:
            # Esto es un parche específico para el caso de Make.com enviando HTML con comillas sin escapar
            # Intentamos encontrar la cadena body y extraerla hasta la última comilla.
            body_start_index = raw_body_str.find('"body": "') + len('"body": "')
            body_end_index = raw_body_str.rfind('"\n}') # Busca la comilla final del body antes de su \n"}
            if body_start_index != -1 and body_end_index != -1 and body_end_index > body_start_index:
                temp_body = raw_body_str[body_start_index:body_end_index]
                # Ahora, reemplazamos las comillas internas si existen en este cuerpo temporal
                # Esta es la lógica que queríamos hacer en Make.com, pero ahora la hacemos en Python
                extracted_body = temp_body.replace('\\"', '"').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
                # Y luego, des-escapamos las comillas dobles que estaban en el original para que BeautifulSoup las vea
                extracted_body = extracted_body.replace('\\"', '"') # Des-escapamos para Beautiful Soup


        # Creamos un objeto que se parezca a EmailInput para pasarlo a Pydantic
        # Si la extracción falla, los valores serán cadenas vacías, Pydantic lo acepta.
        email_input = EmailInput(subject=extracted_subject, body=extracted_body)


        cleaned_body = clean_html_content(email_input.body)
        category = await classification_chain.ainvoke({"subject": email_input.subject, "body": cleaned_body})
        return {"category": category.strip()}

    except ValidationError as e:
        # Errores de validación de Pydantic
        print(f"Error de validación Pydantic: {e.errors()}")
        raise HTTPException(status_code=422, detail=e.errors())
    except HTTPException as e:
        raise e # Re-lanzar HTTPException
    except Exception as e:
        # Otros errores inesperados
        print(f"Error inesperado al clasificar el correo: {e}")
        # Aquí, si la extracción falla, devolver un 400 o 500 y mostrar el error real.
        raise HTTPException(status_code=500, detail=f"Internal server error during classification: {e}. Raw body: {raw_body_str[:200]}...")


@app.post("/generate_response/", summary="Genera una respuesta para un correo", response_description="Texto de la respuesta generada", response_model=ResponseOutput)
async def generate_response_endpoint(request: Request):
    """
    Genera un borrador de respuesta para un correo electrónico
    basado en su contenido y la categoría previamente clasificada.
    """
    try:
        raw_body_str = (await request.body()).decode('utf-8')
        print(f"DEBUG: Raw body received for response: {raw_body_str[:500]}...")

        # Intentar extraer subject, body, category manualmente
        subject_match = re.search(r'"subject":\s*"(.*?)(?<!\\)"', raw_body_str)
        body_match = re.search(r'"body":\s*"(.*?)(?<!\\)"', raw_body_str, re.DOTALL)
        category_match = re.search(r'"category":\s*"(.*?)(?<!\\)"', raw_body_str)

        extracted_subject = subject_match.group(1) if subject_match else ""
        extracted_body = body_match.group(1) if body_match else ""
        extracted_category = category_match.group(1) if category_match else ""

        # Parche similar para el body si las comillas lo rompen
        if not extracted_body and 'dir="' in raw_body_str:
            body_start_index = raw_body_str.find('"body": "') + len('"body": "')
            body_end_index = raw_body_str.rfind('"\n}')
            if body_start_index != -1 and body_end_index != -1 and body_end_index > body_start_index:
                temp_body = raw_body_str[body_start_index:body_end_index]
                extracted_body = temp_body.replace('\\"', '"').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
                extracted_body = extracted_body.replace('\\"', '"') # Des-escapamos para Beautiful Soup


        response_data = ResponseInput(subject=extracted_subject, body=extracted_body, category=extracted_category)


        cleaned_body = clean_html_content(response_data.body)
        response_text = await response_generation_chain.ainvoke({
            "subject": response_data.subject,
            "body": cleaned_body,
            "category": response_data.category
        })
        return {"response_text": response_text.strip()}
    except ValidationError as e:
        print(f"Error de validación Pydantic en respuesta: {e.errors()}")
        raise HTTPException(status_code=422, detail=e.errors())
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error inesperado al generar la respuesta: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error during response generation: {e}. Raw body: {raw_body_str[:200]}...")

# Endpoint de prueba para verificar que la API está funcionando
@app.get("/")
async def read_root():
    return {"message": "API de automatización de correo con LangChain y Gemini funcionando!"}