FROM python:3.12-slim

WORKDIR /app

COPY ./pyproject.toml .

RUN pip install --no-cache-dir -q -e .

COPY . .

EXPOSE 7860

CMD ["python", "src/start_gradio.py"]
