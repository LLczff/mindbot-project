from datetime import datetime, timedelta
from typing import Union
import json

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

############# JWT secret key #############
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


############# Classes #############

class User(BaseModel):
    email: str
    firstname: str
    lastname: str


class TokenData(BaseModel):
    email: Union[str, None] = None


class UserInDB(User):
    hashed_password: str

############# Functions #############

# get database from text file
def get_db(path):
    with open(path) as f:
        try:
            db = json.loads(f.read())
        except json.decoder.JSONDecodeError:
            db = ""
    return db


def create_seat_map(path, col):
    #get occupied seat from text file
    f = open(path,'r')
    lines = f.readlines()
    reserved_seat=[]
    for x in lines:
        reserved_seat.append(x.split()[col])
    f.close()

    #create seat layout
    layout = {}
    for row in ["A","B","C","D","E"]:
        layout[row] = [1]*8
    
    #update occupied seat in seat layout
    for seat in reserved_seat:
        layout[seat[0]][int(seat[1])-1] = 0

    return layout


# check if small list contains in big list
# get position number of available seat
def contains(small: list, big: list):
    seat_number = []
    seat = []
    for i in range(len(big)-len(small)+1):
        for j in range(len(small)):
            if big[i+j] != small[j]:
                break
        else:
            for ind in range(i+1, i+len(small)+1):
                seat.append(ind)
                if len(seat) == len(small):
                    seat_number.append(seat)
                    seat = []
            for seat_group in seat_number:  # make sure that no one seat alone
                if (4 in seat_group) and (5 in seat_group):
                    if (3 not in seat_group) or (6 not in seat_group):
                        seat_number.remove(seat_group)
    return seat_number


def get_seat(layout: dict, seat: int):  # get both row and column seat postion
    availiable_seat = []
    for lst in layout:
        seat_number = contains([1]*seat, layout[lst])
        if seat_number:
            for number_group in seat_number:
                seat_pst = []
                for number in number_group:
                    seat_pst.append(lst+str(number))
                availiable_seat.append(seat_pst)
    return availiable_seat


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db, email: str):
    if email in db:
        user_dict = db[email]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, email: str, password: str):
    user = get_user(fake_db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user_db = get_db('db.txt')
    user = get_user(user_db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


############# API #############
@app.post("/register")
async def register(firstname: str, lastname: str, birth: str, email: str, password: str):
    credentials_exception = HTTPException(
        status_code=status.HTTP_406_NOT_ACCEPTABLE,
        detail="Cannot use this email",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # get data from database
    user_db = get_db('db.txt')

    # check if repeated email
    if email in user_db:
        raise credentials_exception

    # hash password
    password = pwd_context.hash(password)

    # prepare data
    new_user = {email: {'firstname': firstname,
                        'lastname': lastname,
                        'birth': birth,
                        'email': email,
                        'hashed_password': password
                        }}

    # write data to database
    with open('db.txt', 'w') as f:
        if user_db:
            data = user_db | new_user
        else:
            data = new_user
        f.write(json.dumps(data))

    return {"detail": "Register Success", "user": new_user}


@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # get data from database
    user_db = get_db('db.txt')

    user = authenticate_user(user_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    login_time = datetime.utcnow() #get timestamp

    return {"access_token": access_token, "token_type": "bearer", "timestamp": login_time}


@app.get("/database") #authentication and look into database info for testing purpose
async def read_database_info(current_user: User = Depends(get_current_user)):
    db_data = get_db('db.txt')
    return db_data


@app.get("/suggest-booking")
async def suggest_availiable_seat(seat: int, current_user: User = Depends(get_current_user)):
    if seat > 0:
        layout = create_seat_map('reserved.txt', 0)
        all_seat = get_seat(layout, seat)
        if all_seat:
            return {"all_possible_seat": all_seat}
        else:
            return {"details": "Unavailable seat right now"}
    else:
        return {"details": "invalid input"}
