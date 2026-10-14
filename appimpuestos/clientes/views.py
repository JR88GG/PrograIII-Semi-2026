from django.shortcuts import render
from django.http import HttpResponse
# Create your views here.
def hola_mundo(request):
    return HttpResponse("Hola mundo desde clientes")

def SaludoNombre(request, nombre, edad):
    return HttpResponse(f"Hola {nombre}, tienes {edad} años y bienvenido a programación")

def index(request):
    return render(request, 'index.html')