# Bookstore API — автентифікація і захист

## Варіант

- Номер варіанта: **6**
- Схема: **JWT** (djangorestframework-simplejwt)
- Право: **P3** — читання всім; створити — будь-який автентифікований; змінити/видалити — власник книги або член групи `Moderators`
- Throttle: **6 запитів/год** для аноніма · **120 запитів/добу** для користувача
- Інтеграція: **I1** — вкладений автор
- Відеозахист (до 3 хв): <ВСТАВТЕ ПОСИЛАННЯ>

## Запуск

```bash
python3 -m venv venv              # Windows: py -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed             # автори, 30 книг, користувачі й групи
python manage.py runserver
python manage.py test
```

Тестові користувачі (`python manage.py seed`), пароль `pass12345`:

| Користувач | Пошта | Акаунт | Група / роль |
|---|---|---|---|
| alice | alice@kpi.edu.ua | 30 днів | Editors, власниця третини книг |
| bob | bob@lnu.edu.ua | 30 днів | Editors |
| carol | carol@gmail.com | 30 днів | — |
| newbie | newbie@kpi.edu.ua | щойно | Editors |
| moder | moder@gmail.com | 30 днів | Moderators |
| staff | staff@gmail.com | 30 днів | `is_staff` |
| admin | admin@example.com | — | суперкористувач, пароль `admin` |

Книги з seed: `owner` = bob для id 1, 4, 7…; carol для 2, 5, 8…; alice для 3, 6, 9….

## Що зроблено

| Крок | Де |
|---|---|
| Схема JWT: `create` / `refresh` / `logout`, access 15 хв, ротація + чорний список | `core/settings.py` (`SIMPLE_JWT`, `INSTALLED_APPS`), `core/urls.py` |
| Анонім отримує 401, а не 403 | `JWTAuthentication` — єдиний у `DEFAULT_AUTHENTICATION_CLASSES` |
| P3 | `bookstore/permissions.py` → `IsOwnerOrModeratorOrReadOnly`, підключений у `BookViewSet.permission_classes` |
| Throttling `anon 6/hour`, `user 120/day` | `REST_FRAMEWORK` у `core/settings.py` |
| I1 | `bookstore/serializers.py` (`author` вкладений, `author_id` на запис, `owner` рядком), `select_related` у `BookViewSet` |

## Результат тестів

```
$ python manage.py test
Ran 59 tests in 13.325s

OK (skipped=37)
```

37 тестів пропущено: вони стосуються інших варіантів.

## Журнал `curl -i`

Скорочено до статусу, важливих заголовків і тіла. Токени обрізані. `$B` = `http://127.0.0.1:8000/api/v1`, `$ACCESS` / `$REFRESH` — токени alice.

### 1. Вхід і вихід

```
$ curl -i -X POST $B/auth/jwt/create/ -H 'Content-Type: application/json' \
    -d '{"username":"alice","password":"pass12345"}'
HTTP/1.1 200 OK
{"refresh":"eyJhbGciOi...","access":"eyJhbGciOi..."}

$ curl -i $B/books/1/ -H "Authorization: Bearer $ACCESS"
HTTP/1.1 200 OK

$ curl -i -X POST $B/auth/jwt/refresh/ -H 'Content-Type: application/json' -d "{\"refresh\":\"$REFRESH\"}"
HTTP/1.1 200 OK
{"access":"eyJhbGciOi...","refresh":"eyJhbGciOi..."}       # ротація: прийшов НОВИЙ refresh

$ curl -i -X POST $B/auth/jwt/refresh/ ... -d "{\"refresh\":\"$REFRESH\"}"     # той самий, старий refresh
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="api"
{"detail":"Токен занесений у чорний список","code":"token_not_valid"}

$ curl -i -X POST $B/auth/jwt/logout/ ... -d "{\"refresh\":\"$REFRESH2\"}"        # актуальний refresh
HTTP/1.1 200 OK
{}

$ curl -i -X POST $B/auth/jwt/refresh/ ... -d "{\"refresh\":\"$REFRESH2\"}"       # після logout
HTTP/1.1 401 Unauthorized
{"detail":"Токен занесений у чорний список","code":"token_not_valid"}

$ curl -i $B/books/1/ -H "Authorization: Bearer $ACCESS"                          # старий access після logout
HTTP/1.1 200 OK                                                                   # див. питання 3

$ curl -i $B/books/ -H "Authorization: Bearer $REFRESH"                           # refresh замість access
HTTP/1.1 401 Unauthorized
{"detail":"Наданий токен не відповідає жодному типу ключа","code":"token_not_valid",...}

$ curl -i -X POST $B/books/ -H 'Content-Type: application/json' -H "Authorization: Token $ACCESS" -d '{}'
HTTP/1.1 401 Unauthorized                                                         # чужий префікс
WWW-Authenticate: Bearer realm="api"
```

### 2. Право доступу P3: дозволено і заборонено

```
$ curl -i -X POST $B/books/ -H 'Content-Type: application/json' \
    -d '{"title":"X","price":"1","author_id":1}'                                  # анонім
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="api"

$ curl -i $B/books/1/                                                             # анонім читає
HTTP/1.1 200 OK

$ curl -i -X POST $B/books/ ... -H "Authorization: Bearer $CAROL" \
    -d '{"title":"Книга carol","price":"10.00","author_id":2}'                    # будь-який автентифікований створює
HTTP/1.1 201 Created
{"id":31,"title":"Книга carol","author":{"id":2,"name":"Леся Українка"},"price":"10.00","cover":null,"owner":"carol"}

$ curl -i -X PATCH $B/books/3/ ... -H "Authorization: Bearer $BOB" -d '{"title":"Hack"}'    # книга alice
HTTP/1.1 403 Forbidden
{"detail":"У вас нема дозволу робити цю дію."}

$ curl -i -X PATCH $B/books/3/ ... -H "Authorization: Bearer $ALICE" -d '{"title":"Нова назва"}'   # власниця
HTTP/1.1 200 OK

$ curl -i -X DELETE $B/books/6/ -H "Authorization: Bearer $MODER"                 # модератор, книга alice
HTTP/1.1 204 No Content
```

### 3. Throttling: останній дозволений запит і `429`

Свіжий сервер, анонімні запити на публічний `/authors/` (ліміт 6/год):

```
#1 … #6: HTTP/1.1 200 OK
#7:      HTTP/1.1 429 Too Many Requests
         Retry-After: 3600
         {"detail":"Запит було проігноровано. Expected available in 3600 seconds."}

$ curl -i -X POST $B/books/ -H 'Content-Type: application/json' -d '{}'          # анонім, ліміт уже вичерпано
HTTP/1.1 401 Unauthorized                                                         # 401, а не 429 — див. питання 4
```

### 4. Інтеграційна вимога I1

```
$ curl -i $B/books/2/ -H "Authorization: Bearer $ALICE"
HTTP/1.1 200 OK
{"id":2,"title":"Книга 02","author":{"id":3,"name":"Іван Франко"},"price":"120.00","cover":null,"owner":"carol"}

$ curl -i -X POST $B/books/ ... -d '{"title":"X","price":"1","author_id":999}'
HTTP/1.1 400 Bad Request
{"author_id":["Недопустимий первинний ключ \"999\" - об'єкт не існує."]}

$ curl -i -X POST $B/books/ ... -d '{"title":"Нова","price":"10.00","author_id":2}'
HTTP/1.1 201 Created
{"id":32,"title":"Нова","author":{"id":2,"name":"Леся Українка"},"price":"10.00","cover":null,"owner":"alice"}
```

## Журнал помилок

Щонайменше дві помилки, на які ви справді натрапили.

| Що побачили (текст помилки або код) | Причина | Що змінили |
|---|---|---|
| Після коміту зі схемою `test_challenge_header` падав: `AssertionError: False is not true` (анонімний POST на `/books/` не давав `WWW-Authenticate`) | Клас прав ще не було підключено, тому `AllowAny` пускав аноніма, і відповідь була 201, а не 401 | Додав власний клас P3 у `bookstore/permissions.py` і підключив його в `BookViewSet` |
| <ЗАПОВНІТЬ СВОЄЮ> | | |

## Дослідницькі питання

Схема JWT, тож питання про JWT і спільне. Джерела: `rest_framework_simplejwt/tokens.py`, `serializers.py`, `authentication.py`, `rest_framework/views.py` (у `site-packages` вашого venv).

**1. Claims в access і refresh.**
Обидва токени мають однакові claims: `token_type`, `exp`, `iat`, `jti`, `user_id`. Відрізняються значенням `token_type` (`access` чи `refresh`), `exp` (15 хв проти 1 доби) і власним `jti`. Сервер розрізняє їх саме за `token_type`: `Token.verify_token_type()` у `tokens.py` порівнює claim з очікуваним типом класу. Тому refresh, поданий як Bearer, дає 401 (див. журнал, п. 1).

**2. `ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`.**
Перше змушує `/refresh/` повертати нову пару: разом з новим access приходить новий refresh. Друге кладе старий refresh у чорний список (`refresh.blacklist()` у `TokenRefreshSerializer`, `serializers.py`). Разом вони роблять refresh одноразовим: старий уже не працює (журнал, п. 1, повторний refresh → 401). Якщо refresh вкрали, а клієнт уже його використав, зловмисник теж отримає відмову.

**3. Старий access після logout.**
Отримав **200**, тобто logout його не відкликає (журнал, п. 1). Чорний список підключено лише до `RefreshToken`: `BlacklistMixin` є тільки в нього, `AccessToken(Token)` його не має. `JWTAuthentication.authenticate()` перевіряє підпис, `exp` і тип токена й не ходить у базу по чорний список. Access — «безстанний», тож діє до кінця свого життя. Звідси випливає, що `ACCESS_TOKEN_LIFETIME` має бути коротким: це і є максимальне вікно, коли вкрадений access ще працює після logout. 15 хвилин — компроміс між безпекою і частотою оновлень.

**4. Порядок перевірок і чому 401 не витрачає ліміт.**
У `APIView.initial()` (`rest_framework/views.py`, рядки ~419–421) порядок такий: `perform_authentication` → `check_permissions` → `check_throttles`. Анонімний запит на запис зупиняється на `check_permissions` (кидає `NotAuthenticated` → 401), до `check_throttles` він не доходить, тому лічильник не росте. У моєму варіанті це видно в журналі, розд. 3: коли ліміт аноніма (6/год) вичерпано, GET `/authors/` дає 429, а POST на `/books/` усе ще дає 401, а не 429.

Додаткове спостереження: `TokenObtainPairView` у simplejwt не має своїх `throttle_classes`, тому на нього діє глобальний ліміт. Тобто 6 спроб входу на годину з однієї IP-адреси: це заодно захищає від перебору паролів, але робить ліміт аноніма доволі незручним для реальних користувачів.

## Якщо користувались ШІ

Код і чернетку цього README я зробив за допомогою Claude (Anthropic) за умовою завдання: схема JWT, клас P3, throttling, I1, журнал `curl`, чернетки відповідей. <ДОПИШІТЬ, що саме перевірили самі і що виявилось неправильним або не підійшло до вашого коду.>
