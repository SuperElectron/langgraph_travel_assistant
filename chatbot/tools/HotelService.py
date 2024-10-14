import sqlite3
from datetime import date, datetime
from typing import Optional, Union
# from langchain_core.tools import tool


# Hotel Service
class HotelService:
    def __init__(self):
        self.DB = "./database/travel2.sqlite"

    def get_safe_tools(self):
        return [self.search_hotels]

    def get_sensitive_tools(self):
        return [
            self.book_hotel,
            self.update_hotel,
            self.cancel_hotel
        ]

    def search_hotels(self, location: Optional[str] = None,
                      name: Optional[str] = None,
                      price_tier: Optional[str] = None,
                      checkin_date: Optional[Union[datetime, date]] = None,
                      checkout_date: Optional[Union[datetime, date]] = None,
                      ) -> list[dict]:
        """ search_hotels """
        conn = sqlite3.connect(self.DB)
        cursor = conn.cursor()
        query = "SELECT * FROM hotels WHERE 1=1"
        params = []

        if location:
            query += " AND location LIKE ?"
            params.append(f"%{location}%")
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return [dict(zip([column[0] for column in cursor.description], row)) for row in results]

    def book_hotel(self, hotel_id: int) -> str:
        """ book_hotel """
        conn = sqlite3.connect(self.DB)
        cursor = conn.cursor()
        cursor.execute("UPDATE hotels SET booked = 1 WHERE id = ?", (hotel_id,))
        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Hotel {hotel_id} successfully booked."
        else:
            conn.close()
            return f"No hotel found with ID {hotel_id}."

    def update_hotel(
            self, hotel_id: int,
            checkin_date: Optional[Union[datetime, date]] = None,
            checkout_date: Optional[Union[datetime, date]] = None,
    ) -> str:
        """ update_hotel """
        conn = sqlite3.connect(self.DB)
        cursor = conn.cursor()

        if checkin_date:
            cursor.execute("UPDATE hotels SET checkin_date = ? WHERE id = ?", (checkin_date, hotel_id))
        if checkout_date:
            cursor.execute("UPDATE hotels SET checkout_date = ? WHERE id = ?", (checkout_date, hotel_id))

        conn.commit()
        if cursor.rowcount > 0:
            conn.close()
            return f"Hotel {hotel_id} successfully updated."
        else:
            conn.close()
            return f"No hotel found with ID {hotel_id}."

    # @tool
    def cancel_hotel(self, hotel_id: int) -> str:
        """ cancel_hotel """
        conn = sqlite3.connect(self.DB)
        cursor = conn.cursor()
        cursor.execute("UPDATE hotels SET booked = 0 WHERE id = ?", (hotel_id,))
        conn.commit()

        if cursor.rowcount > 0:
            conn.close()
            return f"Hotel {hotel_id} successfully cancelled."
        else:
            conn.close()
            return f"No hotel found with ID {hotel_id}."
