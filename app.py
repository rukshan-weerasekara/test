from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

#database connection

DB_HOST = "aws-0-ap-southeast-1.pooler.supabase.com"
DB_NAME = "postgres"
DB_USER = "postgres.abuivgtzqlblivabscgg"
DB_PASSWORD = "1@Wathsala9927"
DB_PORT = "6543"


encoded_password = quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

with engine.connect() as connection:
   
    connection.execute(text('DROP TABLE IF EXISTS "Hotel"'))

    
    reasons_df = pd.read_sql(text('SELECT * FROM "Reson"'), connection)
    climate_df = pd.read_sql(text('SELECT * FROM "Monthly Climate"'), connection)
    hotel_df = pd.read_sql(text("""
        SELECT hp.hotel_name, p.package_name, p.night_price, p.package_type
        FROM "accounts_hotelprofile" hp
        JOIN "accounts_hotelpackage" p ON hp.id = p.hotel_id
    """), connection)


# Api Logig Part Start

app = FastAPI()

class UserInput(BaseModel):
    climate: str
    reasons: list[str]
    accommodation_type: str  

def generate_grouped_recommendations(climate: str, reasons: list[str]) -> dict:
    filtered_places = reasons_df[
        (reasons_df[climate] == "Yes") &
        (reasons_df.iloc[:, 1:4].apply(lambda x: any(reason in x.values for reason in reasons), axis=1))
    ]
    grouped_recommendations = {}
    for reason in reasons:
        places_for_reason = filtered_places[
            filtered_places.iloc[:, 1:4].apply(lambda x: reason in x.values, axis=1)
        ]["Place"].tolist()
        if places_for_reason:
            grouped_recommendations[reason] = places_for_reason
    return grouped_recommendations

def build_response(grouped_recommendations: dict, best_months: list, accommodation=None, advisory: str = None) -> dict:
    response = {
         "best_months": best_months,
         "recommendations": grouped_recommendations,
    }
    if accommodation is not None:
         response["accommodations"] = accommodation.to_dict('records')
    if advisory:
         response["advisory"] = advisory
    return response


# APi Run Part
@app.post("/generate-recommendations/")
def generate_recommendations(user_input: UserInput):
    climate = user_input.climate.strip().capitalize()
    reasons = [reason.strip() for reason in user_input.reasons]
    accommodation_type = user_input.accommodation_type.strip().capitalize()

    include_accommodations = accommodation_type.lower() != "no"

    if climate not in climate_df["Climate"].unique():
        raise HTTPException(status_code=400, detail="Invalid climate type provided.")

    if climate == "Rainy":
        allowed_reasons = {"Watching Historical Places", "Watching Cultural Places"}
        user_allowed = [reason for reason in reasons if reason in allowed_reasons]
        user_disallowed = [reason for reason in reasons if reason not in allowed_reasons]

        response_data = {}
        if user_allowed:
            grouped_recommendations = {}
            for reason in user_allowed:
                places_for_reason = reasons_df[
                    reasons_df.iloc[:, 1:4].apply(lambda x: reason in x.values, axis=1)
                ]["Place"].tolist()
                if places_for_reason:
                    grouped_recommendations[reason] = places_for_reason
            if grouped_recommendations:
                best_months = climate_df[climate_df["Climate"] == climate]["Month"].tolist()
                if include_accommodations:
                    filtered_hotels = hotel_df[hotel_df["package_type"] == accommodation_type]
                    accommodation = filtered_hotels[["hotel_name", "package_name", "night_price"]]
                else:
                    accommodation = None
                response_data = build_response(grouped_recommendations, best_months, accommodation)
        if user_disallowed:
            advisory_text = (
                "\n Travel Advisory: Rainy Conditions Ahead! \n"
                "🌧 Heavy rains may impact outdoor activities. Please be cautious!\n\n"
                "🔹 Roads and pathways may be slippery.\n"
                "🔹 Increased risk of landslides in certain areas.\n"
                "🔹 Higher chances of encountering venomous snakes.\n\n"
                "💡 Tip: For reasons other than 'Watching Historical Places' or 'Watching Cultural Places', "
                "travel during rainy weather may not be ideal.\n\n"
                "Stay safe & travel wisely with TripHomie! ✨"
            )
            if response_data:
                response_data["advisory"] = advisory_text
            else:
                response_data = {"advisory": advisory_text}
        if response_data:
            return response_data
        else:
            raise HTTPException(status_code=404, detail="No recommendations found for the given inputs.")

    grouped_recommendations = generate_grouped_recommendations(climate, reasons)
    best_months = climate_df[climate_df["Climate"] == climate]["Month"].tolist()
    
    if include_accommodations:
        filtered_hotels = hotel_df[hotel_df["package_type"] == accommodation_type]
        accommodation = filtered_hotels[["hotel_name", "package_name", "night_price"]]
    else:
        accommodation = None

    if grouped_recommendations:
        response_data = build_response(grouped_recommendations, best_months, accommodation)
        return response_data
    else:
        raise HTTPException(status_code=404, detail="No recommendations found for the given inputs.")
