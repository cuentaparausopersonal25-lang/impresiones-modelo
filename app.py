from flask import Flask, render_template
app = Flask(__name__)
PRODUCTS = [
 {"name":"Organizador","price":8000,"symbol":"▤"},
 {"name":"Dragón","price":5000,"symbol":"♜"},
 {"name":"Dragón con lámpara","price":15000,"symbol":"✧"},
 {"name":"Lagartija","price":3000,"symbol":"〰"},
 {"name":"Organizador 2","price":15000,"symbol":"▦"},
 {"name":"Letras personalizadas","price":7000,"symbol":"Aa"},
]
WHATSAPP = "5493875556515"
@app.route("/")
def home():
 return render_template("index.html", products=PRODUCTS, whatsapp=WHATSAPP)
if __name__ == "__main__":
 app.run(debug=True)
