from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    trips = db.relationship("Trip", backref="user", lazy=True)


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.String(20), nullable=False)
    end_date = db.Column(db.String(20), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    destinations = db.relationship(
        "Destination",
        backref="trip",
        lazy=True,
        cascade="all, delete-orphan"
    )


class Destination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    notes = db.Column(db.Text)

    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)


def get_coordinates(city, country):
    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": f"{city}, {country}",
        "format": "json",
        "limit": 1
    }

    headers = {
        "User-Agent": "Travel Planner Flask Project"
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()

        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])

    except Exception as error:
        print("Error getting coordinates:", error)

    return None, None


def get_weather(latitude, longitude):
    if latitude is None or longitude is None:
        return None

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "timezone": "auto"
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        current = data.get("current")

        if current:
            return {
                "temperature": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "wind_speed": current.get("wind_speed_10m"),
                "weather_code": current.get("weather_code")
            }

    except Exception as error:
        print("Error getting weather:", error)

    return None


def weather_description(code):
    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm"
    }

    return weather_codes.get(code, "Unknown")


def get_country_info(country):
    url = f"https://restcountries.com/v3.1/name/{country}"

    try:
        response = requests.get(url)
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            country_data = data[0]

            currencies = country_data.get("currencies", {})
            currency_name = "Not available"

            if currencies:
                first_currency = list(currencies.values())[0]
                currency_name = first_currency.get("name", "Not available")

            languages = country_data.get("languages", {})
            language_list = "Not available"

            if languages:
                language_list = list(languages.values())[0]


            return {
                "official_name": country_data.get("name", {}).get("official", "Not available"),
                "capital": country_data.get("capital", ["Not available"])[0],
                "population": country_data.get("population", "Not available"),
                "region": country_data.get("region", "Not available"),
                "flag": country_data.get("flag", ""),
                "currency": currency_name,
                "languages": language_list
            }

    except Exception as error:
        print("Error getting country info:", error)

    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            return "This email is already registered"

        hashed_password = generate_password_hash(password)

        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("dashboard"))

        return "Email or password incorrect"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    trips = Trip.query.filter_by(user_id=session["user_id"]).all()
    return render_template("dashboard.html", trips=trips)


@app.route("/trips/new", methods=["GET", "POST"])
def new_trip():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]

        new_trip = Trip(
            title=title,
            start_date=start_date,
            end_date=end_date,
            user_id=session["user_id"]
        )

        db.session.add(new_trip)
        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("new_trip.html")


@app.route("/trips/<int:trip_id>")
def trip_detail(trip_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != session["user_id"]:
        return redirect(url_for("dashboard"))

    weather_data = {}
    country_data = {}

    for destination in trip.destinations:
        weather = get_weather(destination.latitude, destination.longitude)

        if weather:
            weather["description"] = weather_description(weather["weather_code"])

        weather_data[destination.id] = weather
        country_data[destination.id] = get_country_info(destination.country)

    return render_template(
        "trip_detail.html",
        trip=trip,
        weather_data=weather_data,
        country_data=country_data
    )


@app.route("/trips/<int:trip_id>/destinations/new", methods=["GET", "POST"])
def new_destination(trip_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != session["user_id"]:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        city = request.form["city"]
        country = request.form["country"]
        notes = request.form["notes"]

        latitude, longitude = get_coordinates(city, country)

        destination = Destination(
            city=city,
            country=country,
            latitude=latitude,
            longitude=longitude,
            notes=notes,
            trip_id=trip.id
        )

        db.session.add(destination)
        db.session.commit()

        return redirect(url_for("trip_detail", trip_id=trip.id))

    return render_template("new_destination.html", trip=trip)


@app.route("/destinations/<int:destination_id>/update-coordinates")
def update_coordinates(destination_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    destination = Destination.query.get_or_404(destination_id)

    if destination.trip.user_id != session["user_id"]:
        return redirect(url_for("dashboard"))

    latitude, longitude = get_coordinates(destination.city, destination.country)

    destination.latitude = latitude
    destination.longitude = longitude

    db.session.commit()

    return redirect(url_for("trip_detail", trip_id=destination.trip_id))


@app.route("/destinations/<int:destination_id>/delete", methods=["POST"])
def delete_destination(destination_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    destination = Destination.query.get_or_404(destination_id)

    if destination.trip.user_id != session["user_id"]:
        return redirect(url_for("dashboard"))

    trip_id = destination.trip_id

    db.session.delete(destination)
    db.session.commit()

    return redirect(url_for("trip_detail", trip_id=trip_id))


@app.route("/trips/<int:trip_id>/delete", methods=["POST"])
def delete_trip(trip_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != session["user_id"]:
        return redirect(url_for("dashboard"))

    db.session.delete(trip)
    db.session.commit()

    return redirect(url_for("dashboard"))

@app.route("/about")
def about():
    return render_template("about.html")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)

