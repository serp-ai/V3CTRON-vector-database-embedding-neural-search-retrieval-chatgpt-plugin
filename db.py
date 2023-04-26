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
        SELECT vc.name, vc.collection_name, vc.embedding_method, vc.description, vc.overview, vc.is_active
        FROM _users u
        INNER JOIN _vector_chat_api_keys vcak
            ON u.user_id = vcak.user_id
        INNER JOIN _vector_collections vc
            ON u.user_id = vc.user_id AND vc.is_active = 1
        WHERE vcak.api_key = %s
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


async def add_collection_to_db(api_key: str, name: str, collection_name: str, embedding_method: str, overview: str, description: str, is_active: bool, db: mysql.connector.MySQLConnection):
    try:
        cursor = db.cursor()
        query = """
        INSERT INTO _vector_collections (user_id, name, collection_name, embedding_method, overview, description, is_active)
        SELECT u.user_id, %s, %s, %s, %s, %s, %s
        FROM _users u
        INNER JOIN _vector_chat_api_keys vcak
            ON u.user_id = vcak.user_id
        WHERE vcak.api_key = %s AND vcak.is_active = 1
        """
        if is_active is None:
            is_active = False
        cursor.execute(query, (name, collection_name, embedding_method, overview, description, is_active, api_key))
        db.commit()
        return True
    except Exception as e:
        print("Error:", e)
        return False


async def update_collection_in_db(api_key: str, name: str, new_name: str, overview: str, description: str, is_active: bool, db: mysql.connector.MySQLConnection):
    try:
        cursor = db.cursor()
        # Start constructing the query
        query = """
        UPDATE _vector_collections vc
        INNER JOIN _users u
            ON vc.user_id = u.user_id
        INNER JOIN _vector_chat_api_keys vcak
            ON u.user_id = vcak.user_id
        SET
        """

        # Add fields to update and their values
        update_fields = []
        values = []

        if new_name is not None:
            update_fields.append("vc.name = %s")
            values.append(new_name)

        if overview is not None:
            update_fields.append("vc.overview = %s")
            values.append(overview)

        if description is not None:
            update_fields.append("vc.description = %s")
            values.append(description)

        if is_active is not None:
            update_fields.append("vc.is_active = %s")
            values.append(is_active)

        # Join the update fields in the query
        query += ", ".join(update_fields)

        # Add the WHERE clause
        query += """
        WHERE vc.name = %s AND vcak.api_key = %s
        """

        # Add the name and API key to the values list
        values.extend([name, api_key])

        # Execute the query
        cursor.execute(query, values)
        db.commit()
        return True
    except Exception as e:
        print("Error:", e)
        return False
    

async def delete_collection_from_db(api_key: str, name: str, db: mysql.connector.MySQLConnection):
    try:
        cursor = db.cursor()
        query = """
        DELETE vc
        FROM _vector_collections vc
        INNER JOIN _users u
            ON vc.user_id = u.user_id
        INNER JOIN _vector_chat_api_keys vcak
            ON u.user_id = vcak.user_id
        WHERE vc.name = %s AND vcak.api_key = %s
        """
        cursor.execute(query, (name, api_key))
        db.commit()
        return True
    except Exception as e:
        print("Error:", e)
        return False
