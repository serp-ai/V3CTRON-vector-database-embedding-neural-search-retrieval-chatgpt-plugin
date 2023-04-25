import os
import random
import string
import mysql.connector


def generate_random_string(length: int = 32) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=length))


def dictfetchall(cursor):
    """
    Return all rows from a cursor as a dict

    Parameters:
        cursor (cursor): Cursor object

    Returns:
        rows (list): List of rows
    """
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


def get_db():
    db = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
    )
    try:
        yield db
    finally:
        db.close()


def authenticate_user(api_key: str, db: mysql.connector.MySQLConnection):
    cursor = db.cursor()
    query = """
    SELECT COUNT(*)
    FROM _users u
    INNER JOIN _vector_chat_api_keys vcak
        ON u.user_id = vcak.user_id
    WHERE vcak.api_key = %s AND vcak.is_active = 1
    """
    cursor.execute(query, (api_key,))
    count = cursor.fetchone()[0]

    return count > 0


async def get_collections_from_db(api_key: str, db: mysql.connector.MySQLConnection, return_only_names_and_overviews: bool = True):
    cursor = db.cursor()
    if return_only_names_and_overviews:
        query = """
        SELECT vc.name, vc.overview
        FROM _users u
        INNER JOIN _vector_chat_api_keys vcak
            ON u.user_id = vcak.user_id
        INNER JOIN _vector_collections vc
            ON u.user_id = vc.user_id AND vc.is_active = 1
        WHERE vcak.api_key = %s AND vcak.is_active = 1
        """
    else:
        query = """
        SELECT vc.name, vc.collection_name, vc.embedding_method, vc.description, vc.overview
        FROM _users u
        INNER JOIN _vector_chat_api_keys vcak
            ON u.user_id = vcak.user_id
        INNER JOIN _vector_collections vc
            ON u.user_id = vc.user_id AND vc.is_active = 1
        WHERE vcak.api_key = %s AND vcak.is_active = 1
        """
    cursor.execute(query, (api_key,))

    return dictfetchall(cursor)


async def get_collection_from_db(api_key: str, collection_name: str, db: mysql.connector.MySQLConnection):
    cursor = db.cursor()
    query = """
    SELECT vc.collection_name, vc.embedding_method
    FROM _users u
    INNER JOIN _vector_chat_api_keys vcak
        ON u.user_id = vcak.user_id
    INNER JOIN _vector_collections vc
        ON u.user_id = vc.user_id AND vc.is_active = 1
    WHERE vcak.api_key = %s AND vcak.is_active = 1 AND vc.name = %s
    """
    cursor.execute(query, (api_key, collection_name))
    collection = cursor.fetchone()

    return collection


async def add_collection_to_db(api_key: str, name: str, collection_name: str, embedding_method: str, overview: str, description: str, db: mysql.connector.MySQLConnection):
    try:
        cursor = db.cursor()
        query = """
        INSERT INTO _vector_collections (user_id, name, collection_name, embedding_method, overview, description, is_active)
        SELECT u.user_id, %s, %s, %s, %s, %s, 1
        FROM _users u
        INNER JOIN _vector_chat_api_keys vcak
            ON u.user_id = vcak.user_id
        WHERE vcak.api_key = %s AND vcak.is_active = 1
        """
        cursor.execute(query, (name, collection_name, embedding_method, overview, description, api_key))
        db.commit()
        return True
    except Exception as e:
        print("Error:", e)
        return False

