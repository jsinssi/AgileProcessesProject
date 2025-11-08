from flask import jsonify
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId

# MongoDB connection setup
client = MongoClient('mongodb://localhost:27017/')
db = client['library']
ratings_collection = db['user_ratings']

def validate_user_ratings_collection():
            """
            Validate that the user_ratings collection exists and has the required fields.
            
            Returns:
                dict: Response with status and message
            """
            try:
                # Check if the collection exists
                if 'user_ratings' not in db.list_collection_names():
                    return jsonify({
                        "status": "error",
                        "message": "The user_ratings collection does not exist."
                    }), 500
                
                # Check for required fields in the first document
                sample_doc = ratings_collection.find_one()
                required_fields = ['user_id', 'book_id', 'rating']
                
                if not all(field in sample_doc for field in required_fields):
                    return jsonify({
                        "status": "error",
                        "message": "The user_ratings collection is missing required fields."
                    }), 500
                
                return jsonify({
                    "status": "success",
                    "message": "The user_ratings collection is valid."
                }), 200

            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": f"Validation error: {str(e)}"
                }), 500

def add_or_update_rating(user_id, book_id, rating):
    """
    Add or update a book rating for a user in MongoDB.
    
    Args:
        user_id (str): The ID of the user
        book_id (str): The ID of the book
        rating (int): Rating value (1-5)
        
    Returns:
        dict: Response with status and message
    """
    try:
        # Validate rating value
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({
                "status": "error",
                "message": "Rating must be an integer between 1 and 5"
            }), 400

        current_time = datetime.now()
        
        # Check if rating exists and update or insert accordingly
        result = ratings_collection.update_one(
            {"user_id": user_id, "book_id": book_id},
            {
                "$set": {
                    "rating": rating,
                    "modified_date": current_time
                },
                "$setOnInsert": {
                    "created_date": current_time
                }
            },
            upsert=True
        )

        message = "Rating updated successfully" if result.matched_count else "Rating added successfully"
        
        return jsonify({
            "status": "success",
            "message": message
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Database error: {str(e)}"
        }), 500

def get_user_rating(user_id, book_id):
    """
    Get the current rating for a specific book by a user from MongoDB.
    
    Args:
        user_id (str): The ID of the user
        book_id (str): The ID of the book
        
    Returns:
        dict: Response with rating information
    """
    try:
        rating_doc = ratings_collection.find_one(
            {"user_id": user_id, "book_id": book_id}
        )
        
        if rating_doc:
            return jsonify({
                "status": "success",
                "rating": rating_doc["rating"],
                "created_date": rating_doc["created_date"],
                "modified_date": rating_doc.get("modified_date")
            }), 200
        else:
            return jsonify({
                "status": "success",
                "message": "No rating found for this book"
            }), 404

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Database error: {str(e)}"
        }), 500