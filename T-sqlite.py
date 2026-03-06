import sqlite3

connection = sqlite3.connect('T-sqlite.db')
cursor = connection.cursor()

cursor.execute('create table users (userID integer primary key, userName text, password text)')

list = [(1, 'admin', 'admin123'), (2, 'user1', 'user123'), (3, 'user2', 'user123')]
cursor.executemany('insert into users values (?, ?, ?)', list)

for row in cursor.execute('select * from users'):
    print(row)

connection.close()