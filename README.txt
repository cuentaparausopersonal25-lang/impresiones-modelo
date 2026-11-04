IMPRESIONES MODELO - versión ampliada

Estructura:
- app.py: aplicación Flask, base SQLite y rutas.
- templates/: páginas de inicio, login y administración.
- static/style.css: diseño adaptable a celular.
- static/uploads/: imágenes cargadas desde el panel.

Ejecutar localmente:
1) python -m pip install -r requirements.txt
2) En Windows CMD:
   set ADMIN_ARIA_PASSWORD=UnaClaveSegura
   set ADMIN_PEDRO_PASSWORD=OtraClaveSegura
   set SECRET_KEY=UnaClaveLargaYPrivada
3) python app.py
4) Abrir http://127.0.0.1:5000

Render:
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
Variables de entorno obligatorias:
ADMIN_ARIA_PASSWORD = contraseña privada de Aria
ADMIN_PEDRO_PASSWORD = contraseña privada de Pedro
SECRET_KEY = cadena larga, aleatoria y privada
DATABASE_PATH = /var/data/tienda.db
UPLOAD_FOLDER = /var/data/uploads (si se configura un Persistent Disk montado en /var/data)

Para persistencia en Render, crear un Persistent Disk y montarlo en /var/data. Sin disco persistente, la base de datos y las imágenes pueden perderse al reiniciar o volver a desplegar el servicio.

Compras: la web NO procesa pagos. Todos los pedidos y consultas se realizan por WhatsApp.
Compra de prueba: simulación informativa por 24 horas, sin cobros.
Compra anticipada: muestra disponibilidad y fecha estimada, pero deriva el pedido a WhatsApp.

Seguridad: configurar contraseñas y SECRET_KEY en Render; no publicarlas en GitHub. Esta versión es una base funcional inicial, no incluye recuperación de contraseña ni registro público de administradores.
