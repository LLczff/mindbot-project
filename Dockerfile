FROM python:3.10

WORKDIR /mindbot-app

ADD main.py /mindbot-app/

ADD db.txt /mindbot-app/

ADD reserved.txt /mindbot-app/

COPY ./requirements.txt /mindbot-app/requirements.txt

RUN pip install -r requirements.txt

CMD ["uvicorn", "main:app","--host","0.0.0.0","--port","8000"]
