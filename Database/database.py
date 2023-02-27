from datetime import date
from time import time
import psycopg2
from typing import Optional, Union
import configparser
from psycopg2.extras import NumericRange

userConn = psycopg2.connect(database='bot', user='parsing', password='papga', port='5432')
userConn.autocommit = True
userCursor = userConn.cursor()

floodConn = psycopg2.connect(database='flood', user='pargsing', password='papga', port='5432')
floodConn.autocommit = True
floodCursor = floodConn.cursor()

parsingConn = psycopg2.connect(database='parsing', user='parsing', password='papga', port='5432')
parsingConn.autocommit = True
parsingCursor = parsingConn.cursor()

shopConn = psycopg2.connect(database='shop', user='parsing', password='papga', port='5432')
shopConn.autocommit = True
shopCursor = shopConn.cursor()


def createdb() -> None:
    """Функция для создания БД"""
    userCursor.execute(
        f'CREATE TABLE IF NOT EXISTS Telegram(ID BIGINT, is_buyed BOOLEAN, buy_date DATE, expired_date DATE, records TEXT, attempts INTEGER, lastrow INT4RANGE NOT NULL, leftlists INTEGER, is_applied BOOLEAN, rowid INTEGER GENERATED ALWAYS AS IDENTITY);')
    userCursor.execute('CREATE TABLE IF NOT EXISTS blacklist(ID INTEGER, reason TEXT);')
    userCursor.execute('CREATE TABLE IF NOT EXISTS balance(ID INTEGER, balance INTEGER);')
    userCursor.execute(
        'CREATE TABLE IF NOT EXISTS QIWI(UID INTEGER, trid INTEGER, sum INTEGER, date TEXT, rowid INTEGER GENERATED ALWAYS AS IDENTITY);')
    userCursor.execute('INSERT INTO balance VALUES (560035353, -999) ON CONFLICT DO NOTHING;')
    userCursor.execute('INSERT INTO balance VALUES (372611602, -999) ON CONFLICT DO NOTHING;')

    # userCursor.execute('''INSERT INTO Telegram VALUES (YOURID, TRUE, '2021-01-01', '2099-12-01', '0', 99999, '[0, 2]', 99999, TRUE) ON CONFLICT DO NOTHING;''')

    parsingCursor.execute(
        'CREATE TABLE IF NOT EXISTS parsed(nickname TEXT, donate TEXT, server TEXT, p_date DATE, rowid INTEGER GENERATED ALWAYS AS IDENTITY);')

    floodCursor.execute('''CREATE TABLE IF NOT EXISTS flood(uid INTEGER, timestamp INTEGER);''')

    shopCursor.execute('''CREATE TABLE IF NOT EXISTS openaccounts(username TEXT, password TEXT, donate TEXT, server TEXT, price INTEGER, additionalauth BOOLEAN DEFAULT FALSE, rowid INTEGER GENERATED ALWAYS AS IDENTITY);''')
    shopCursor.execute('''CREATE TABLE IF NOT EXISTS buyedaccounts(username TEXT, password TEXT, donate TEXT, server TEXT, price INTEGER, additionalauth BOOLEAN, rowid INTEGER);''')


class Shop:
    async def getprice(lotid: int) -> Union[tuple, None]:
        """Получение цены по ID лота"""
        shopCursor.execute(f'''SELECT username, donate, price FROM openaccounts WHERE rowid = {lotid};''')
        data = shopCursor.fetchone()
        return data

    async def remove(lotid: int) -> None:
        """Удаление купленных лотов"""
        shopCursor.execute(f'''INSERT INTO buyedaccounts (username, password, donate, server, price, additionalauth, rowid) (SELECT * FROM openaccounts WHERE rowid = {lotid});''')
        shopCursor.execute(f'''DELETE FROM openaccounts WHERE rowid = {lotid};''')

    async def buy(lotid: int, uid: int) -> Union[bool, str, None]:
        """Получение всех деталей (покупка) аккаунта из магазина"""
        shopCursor.execute(f'''SELECT * FROM openaccounts WHERE rowid = {lotid};''')
        data = shopCursor.fetchone()

        if data is not None:
            price = data[4]
            if await Bot.Bank.buy(uid, price):
                await Shop.remove(lotid)
                return data
            else:
                return 'Недостаточно средств на счету'

        else:
            return 'Аккаунта в продаже не найдено, деньги с баланса не списаны.\n\n Вероятно, лот продан... Или его попросту не существует'

    @staticmethod
    def returnaccounts() -> Union[tuple, None]:
        """Все аккаунты которые есть в открытой БД"""
        shopCursor.execute(f'''SELECT username, donate, server, price, rowid FROM openaccounts;''')
        data = shopCursor.fetchall()
        return data


class Parsing:  # ПАРСИНГ РЕШЕНО ОСТАВИТЬ СИНХРОННЫМ
    def addpars(nickname: str, donate: str, server: str, dates: str) -> None:
        """Добавление спаршенных данных"""
        parsingCursor.execute(f'''INSERT INTO parsed VALUES ('{nickname}', '{donate}', '{server}', '{dates}');''')

    def checkpars(donate: str, nickname: str, server: str) -> bool:
        """Проверка парсинга"""
        parsingCursor.execute(f'''SELECT nickname FROM parsed WHERE nickname = '{nickname}' AND donate = '{donate}' AND server = '{server}';''')
        nickn = parsingCursor.fetchone()

        if nickn is not None and nickn != '':
            return True
        else:
            return False

    def data(server: str, nickname: str) -> Union[tuple, None]:
        """Вывод всех данных по юзеру на сервере"""
        parsingCursor.execute(f'''SELECT * FROM parsed WHERE nickname = '{nickname}' AND server = '{server}';''')
        data = parsingCursor.fetchone()

        if data is not None:
            return data
        else:
            return None

    def getnickname(nickname: str, server: str) -> Union[tuple, None]:
        parsingCursor.execute(f'''SELECT * FROM parsed WHERE nickname = '{nickname}' AND server = '{server}';''')
        info = parsingCursor.fetchone()

        if info is not None and info != '':
            return info
        else:
            return None


class Bot:
    config = configparser.ConfigParser()
    config.read('config.ini')

    maxlists = config.getint('market', 'listslimit')
    vips = [YOURID]

    class Blacklist:
        async def blacklist(uid: int, reason: Optional[str] = None) -> True:
            """Внесение в ЧС"""
            if reason is not None:
                userCursor.execute(f'''INSERT INTO blacklist VALUES ({uid}, '{reason}') ON CONFLICT DO NOTHING;''')
            else:
                userCursor.execute(f'INSERT INTO blacklist VALUES ({int(uid)}) ON CONFLICT DO NOTHING;')
            return True

        async def checkbl(uid: int) -> bool:
            """Проверка на ЧС"""
            if await Bot.TgTools.antiflood(uid):
                return True

            userCursor.execute(f'SELECT ID FROM blacklist WHERE ID = {uid};')
            output = userCursor.fetchone()
            if output is None:
                return False
            else:
                return True

    class Bank:
        async def apply(uid: int) -> None:
            """Функция подтверждения и согласия с условиями пополнения кивоса, платежку в будущем сменю в соответствии с планом"""
            userCursor.execute(f'UPDATE Telegram SET is_applied = TRUE WHERE ID = {uid};')

        async def balance(uid: int) -> Union[int, None]:
            """Баланс юзверя"""
            if uid in Bot.vips:
                return 9999999

            userCursor.execute(f'SELECT balance FROM balance WHERE ID = {uid};')
            output, = userCursor.fetchone()
            return output

        async def checkapply(uid: int) -> Union[bool, None]:
            """Проверка на подтверждение"""
            userCursor.execute(f'SELECT is_applied FROM Telegram WHERE ID = {uid};')
            try:
                result, = userCursor.fetchone()
            except TypeError:
                return False
            return result

        async def balanceup(uid: int, datez: Union[int, str], transaction_id: int, trsum: int) -> None:
            """Увеличение баланса"""
            userCursor.execute(f'''INSERT INTO QIWI VALUES ({int(uid)}, {transaction_id}, {trsum}, '{datez}');''')
            bal = int(await Bot.Bank.balance(uid) + trsum)

            userCursor.execute(f'UPDATE balance SET balance = {bal} WHERE ID = {uid};')

        async def buy(uid: int, sumt: int) -> Union[bool, None]:
            """Покупка чего-то (в основном для магазина)"""
            if uid in Bot.vips:
                return True

            balance = int(await Bot.Bank.balance(uid)) - sumt
            if balance < 0 and uid not in Bot.vips:
                return False
            else:
                userCursor.execute(f'UPDATE balance SET balance = {balance} WHERE ID = {uid};')
                return True

        async def buysub(uid: int, subprice: int) -> [str, None]:
            """Покупка подписки"""
            balance = int(await Bot.Bank.balance(uid)) - subprice
            if balance < 0:
                return 'Недостаточно средств'
            date_today = date.today()

            try:
                dateexp = date_today.replace(month=date_today.month + 3)
            except ValueError:
                month = date_today.month - 9
                year = date_today.year + 1
                dateexp = date_today.replace(year=year, month=month)

            userCursor.execute(f'UPDATE balance SET balance = {balance} WHERE ID = {uid};')
            userCursor.execute(f'UPDATE Telegram SET is_buyed = TRUE WHERE ID = {uid};')
            userCursor.execute(f'UPDATE Telegram SET leftlists = {Bot.maxlists} WHERE ID = {uid};')
            userCursor.execute(f'''UPDATE Telegram SET buy_date = '{date_today}' WHERE ID = {uid};''')
            userCursor.execute(f'''UPDATE Telegram SET expired_date = '{dateexp}' WHERE ID = {uid};''')

            return 'Операция прошла успешно'

    class Sublists:
        async def attemptlists(uid: int) -> Union[bool, int, None]:
            """Проверяет остатки по листам у юзверя"""
            userCursor.execute(f'SELECT leftlists FROM Telegram WHERE ID = {uid};')
            try:
                output, = userCursor.fetchone()
            except Exception as e:
                print(e)
                return False

            return output

        async def generatelist(userid: int) -> Union[list, bool, None]:
            """Генерация (первичное взятие данных с БД) листов для подписок"""
            userCursor.execute(f'''SELECT lastrow FROM Telegram WHERE ID = {userid};''')
            try:
                lastrowid, = userCursor.fetchone()
            except TypeError:
                lastrowid = NumericRange(1, 3)

            parsingCursor.execute(
                f'''SELECT rowid FROM parsed WHERE rowid NOT BETWEEN {lastrowid.lower - 10} AND {lastrowid.upper - 1} ORDER BY random() LIMIT 1;''')  # NumericRange выдает последнее значение на 1 больше чем было задано
            rowid, = parsingCursor.fetchone()

            parsingCursor.execute(f'SELECT * FROM parsed WHERE rowid >= {rowid} LIMIT 10;')
            data = parsingCursor.fetchall()  # list <tuple>
            balcheck = await Bot.Sublists.attemptlists(userid)

            if balcheck <= 0:
                return False

            userCursor.execute(f'''UPDATE Telegram SET lastrow = '[{rowid}, {rowid + 10}]' WHERE ID = {userid};''')
            await Bot.Sublists.decreaselists(userid)

            return data

        async def decreaselists(uid: int) -> Union[int, None]:
            """Уменьшает листы юзверя"""
            userCursor.execute(f'SELECT leftlists FROM Telegram WHERE ID = {uid};')
            output, = userCursor.fetchone()
            userCursor.execute(f'''UPDATE Telegram SET leftlists = {output - 1} WHERE ID = {uid};''')

            if output is None:
                return None
            else:
                return output

    class TgTools:
        async def antiflood(uid: int) -> Union[bool, None]:
            """Функция от флуда"""
            floodCursor.execute(f'''INSERT INTO flood VALUES ({uid}, {time()});''')

            floodCursor.execute(f'''SELECT uid FROM flood WHERE uid = {uid} AND timestamp > {int(time()) - 10};''')
            data = floodCursor.fetchall()

            if len(data) >= 10:
                await Bot.Blacklist.blacklist(uid, 'Флуд командами')
                return True
            else:
                return False

        async def attempts(uid: int) -> Union[int, None]:
            """Проверяет попытки юзверя на пополнение кивоса"""
            userCursor.execute(f'SELECT attempts FROM Telegram WHERE ID = {uid};')
            output, = userCursor.fetchone()

            if output is None:
                return None
            else:
                return output

        async def updateattempts(uid: int, number: int) -> bool:
            """Обновление (обычно обнуление) попыток"""
            userCursor.execute(f'UPDATE Telegram SET attempts = {number} WHERE ID = {int(uid)};')
            return True

        async def checkuser(uid: str) -> Union[int, None]:
            """Проверка, есть ли юзер в БД или нет"""
            userCursor.execute(f'SELECT ID FROM Telegram WHERE ID = {uid};')
            if userCursor.fetchone() is not None:
                return True
            else:
                return False

        async def subscription(uid: int) -> Union[bool, None]:
            """Проверка на подпиську"""
            userCursor.execute(f'SELECT is_buyed FROM Telegram WHERE ID = {int(uid)};')
            result, = userCursor.fetchone()

            return result

        async def start(uid: int) -> Union[bool, None]:
            """Стартовая функция для юзверей"""
            userCursor.execute(f'''INSERT INTO Telegram VALUES({uid}, FALSE, null, null, '', 3, '[0, 2]', 0, FALSE);''')
            if uid != 560035353:
                userCursor.execute(f'INSERT INTO balance VALUES({uid}, 0);')
            else:
                return True
            return True

    class ScheduleTools:
        def setall(maxlists: int) -> None:
            """Обнуление попыток для купивших подпыську"""
            userCursor.execute(f'UPDATE Telegram SET leftlists = {maxlists} WHERE is_buyed = TRUE;')

        @staticmethod
        async def floodvacuum() -> None:
            """Очистка устаревших записей надзора за флудом чтобы не засорять БД"""
            floodCursor.execute(f'''DELETE FROM flood WHERE timestamp < {int(time()) - 10};''')

        @staticmethod
        async def clearexpired() -> None:
            """Удаление подписок у юзеров, у которых подписки просрочены"""
            userCursor.execute(
                f'''UPDATE Telegram SET is_buyed = FALSE, buy_date = null, expired_date = null, leftlists = 0 WHERE expired_date <= '{date.today()}';''')


class Debugging:
    def generateparses(ccount: int, dtime: str):
        for i in range(ccount):
            parsingCursor.execute(f'''INSERT INTO parsed VALUES ('{i}', '{i}', 'debug', '{dtime}');''')
        return True

    def generateshop(ccount: int):
        for i in range(ccount):
            shopCursor.execute(f'''INSERT INTO openaccounts VALUES ('{i}', '{i}', '{i}', 'debug', 1);''')
        return True
