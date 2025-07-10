import os
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import json
import re

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

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY)

# Modelos Pydantic
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

# Plantillas y Cadenas
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

# Función para limpiar HTML (¡Esta es la clave!)
def clean_html_content(html_content: str) -> str:
    if not html_content:
        return ""
    # Aseguramos que solo se procese si es una cadena y no un valor nulo/vacío
    if isinstance(html_content, str):
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    return html_content # Devolvemos sin cambios si no es una cadena (aunque no debería pasar)

# Endpoints
@app.post("/classify_email/", summary="Clasifica un correo electrónico", response_description="Categoría del correo clasificado", response_model=CategoryOutput)
async def classify_email_endpoint(request: Request):
    try:
        raw_body_str = (await request.body()).decode('utf-8')
        print(f"DEBUG: Raw body received for classification: {raw_body_str[:500]}...")

        subject_match = re.search(r'"subject":\s*"(.*?)(?<!\\)"', raw_body_str)
        body_match = re.search(r'"body":\s*"(.*?)(?<!\\)"', raw_body_str, re.DOTALL)

        extracted_subject = subject_match.group(1) if subject_match else ""
        extracted_body = body_match.group(1) if body_match else ""

        if not extracted_body and 'dir="' in raw_body_str:
            body_start_index = raw_body_str.find('"body": "') + len('"body": "')
            # Ajustamos la búsqueda del final del body para ser más robusta
            # Buscamos la última comilla que no sea escapada, seguida opcionalmente de \n"}\n
            body_end_match = re.search(r'(?<!\\)"(?:\n"|\n}\n)?\s*$', raw_body_str[body_start_index:], re.DOTALL)
            if body_end_match:
                body_end_index = body_start_index + body_end_match.start()
                temp_body = raw_body_str[body_start_index:body_end_index]
                # Limpiamos las barras invertidas de escapes JSON para que BeautifulSoup lo vea correctamente
                extracted_body = temp_body.replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r')
            else:
                extracted_body = "" # Fallback si el regex no encuentra el final

        email_input = EmailInput(subject=extracted_subject, body=extracted_body)

        # ¡Aquí es donde se limpia el body antes de pasarlo a Gemini para clasificación!
        cleaned_body = clean_html_content(email_input.body)
        print(f"DEBUG: Cleaned body for classification: {cleaned_body[:500]}...") # Añadido para depuración

        category = await classification_chain.ainvoke({"subject": email_input.subject, "body": cleaned_body})
        return {"category": category.strip()}

    except ValidationError as e:
        print(f"Error de validación Pydantic: {e.errors()}")
        raise HTTPException(status_code=422, detail=e.errors())
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error inesperado al clasificar el correo: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error during classification: {e}. Raw body: {raw_body_str[:200]}...")

@app.post("/generate_response/", summary="Genera una respuesta para un correo", response_description="Texto de la respuesta generada", response_model=ResponseOutput)
async def generate_response_endpoint(request: Request):
    try:
        raw_body_str = (await request.body()).decode('utf-8')
        print(f"DEBUG: Raw body received for response: {raw_body_str[:500]}...")

        subject_match = re.search(r'"subject":\s*"(.*?)(?<!\\)"', raw_body_str)
        body_match = re.search(r'"body":\s*"(.*?)(?<!\\)"', raw_body_str, re.DOTALL)
        category_match = re.search(r'"category":\s*"(.*?)(?<!\\)"', raw_body_str)

        extracted_subject = subject_match.group(1) if subject_match else ""
        extracted_body = body_match.group(1) if body_match else ""
        extracted_category = category_match.group(1) if category_match else ""

        if not extracted_body and 'dir="' in raw_body_str:
            body_start_index = raw_body_str.find('"body": "') + len('"body": "')
            body_end_match = re.search(r'(?<!\\)"(?:\n"|\n}\n)?\s*$', raw_body_str[body_start_index:], re.DOTALL)
            if body_end_match:
                body_end_index = body_start_index + body_end_match.start()
                temp_body = raw_body_str[body_start_index:body_end_index]
                extracted_body = temp_body.replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r')
            else:
                extracted_body = "" # Fallback

        response_data = ResponseInput(subject=extracted_subject, body=extracted_body, category=extracted_category)

        # ¡Aquí es donde se limpia el body antes de pasarlo a Gemini para generar la respuesta!
        cleaned_body = clean_html_content(response_data.body)
        print(f"DEBUG: Cleaned body for response: {cleaned_body[:500]}...") # Añadido para depuración

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