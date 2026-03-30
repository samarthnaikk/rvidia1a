FROM python:3.11-slim
WORKDIR /app
COPY run.py .
RUN pip install Flask
EXPOSE 8000
CMD ["python", "run.py"]
