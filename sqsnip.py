import sqlite3

def select_elements(
        table: list,
        where_state: bool = False
    ):
    result = ""
    if type(table) == list:
        params = [len(table), 0]
        for el in table:
            if type(el) == dict:
                if len(el) > 1:
                    for i in el:
                        el[i] = f"\"{el[i]}\"" if type(el[i]) == str else str(el[i])
                        res = ", " if not where_state else " AND "
                        result += str(i) + " = " + el[i] + ("" if params[1] == params[0] else res)
                        params[1] += 1
                else:
                    params[1] += 1
                    for i in el:
                        el[i] = f"\"{el[i]}\"" if type(el[i]) == str else str(el[i])
                        res = ", " if not where_state else " AND "
                        result += str(i) + " = " + el[i] + ("" if params[1] == params[0] else res)
            else:
                params[1] += 1
                res = ", " if not where_state else " AND "
                result += str(el) + ("" if params[1] == params[0] else res)
    elif type(table) == str:
        result = table
    elif type(table) == dict:
        params = [len(table), 0]
        for el in table:
            params[1] += 1
            table[el] = f"\"{table[el]}\"" if type(table[el]) == str else str(table[el])
            res = ", " if not where_state else " AND "
            result += str(el) + " = " + table[el] + ("" if params[1] == params[0] else res)
    return result

class database:
    def __init__(
            self, 
            db_name: str,
            db_table: str,
            db_values: str
        ):
        self.db = sqlite3.connect(db_name)
        self.sql = self.db.cursor()
        self.table = db_table

        self.sql.execute(f"""CREATE TABLE IF NOT EXISTS {db_table}({db_values})""")
        self.db.commit()

    def select(self, need: list[dict] | str, where: str | dict | list[dict], all_state = False) -> dict | None:
        result = ["", ""]
        
        if type(need) == str:
            result[0] = need
        elif type(need) == list:
            params = [len(need), 0]
            for el in need:
                params[1] += 1
                result[0] += str(el) + ("" if params[1] == params[0] else ", ")

        result[1] = select_elements(where, True)

        print(result[1])
        self.sql.execute(f"SELECT {result[0]} FROM {self.table} WHERE {result[1]}")
        result = self.sql.fetchone() if not all_state else self.sql.fetchall()

        if result and len(result) == 0:
            return None
        
        return result
    
    def insert(self, values: list | tuple | dict):
        if type(values) == list or dict:
            values = tuple(values)
        
        keys = "("
        for i in range(len(values)):
            if i != (len(values) - 1):
                keys += "?,"
            else:
                keys += "?)"
        self.sql.execute(f"INSERT INTO {self.table} VALUES {keys}", values)
        self.db.commit()

    def update(self, keys: str | dict | list[dict],  where: str | dict | list[dict]):
        result = ["", ""]

        result[0] = select_elements(keys)
        result[1] = select_elements(where, True)

    
        self.sql.execute(f"UPDATE {self.table} SET {result[0]} WHERE {result[1]}")
        self.db.commit()


    def close(self):
        self.db.close()

