"""Module to handle dumping data to google sheets (happens in scheduler and parse_settings)"""
import os
import sys
from functools import reduce
from datetime import date, timedelta,datetime
from dotenv import load_dotenv
import logging
import gspread
import numpy as np
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json
import connect_to_database

load_dotenv()

logger = logging.getLogger()
logging.basicConfig(stream=sys.stdout)
logger.setLevel(logging.INFO)

local_dev = os.getenv("LOCAL_DEV") == "true"


def init_sheets(creds):
    """Function to initialize google sheets API uses credentials in an env var"""
    if local_dev: 
        json_creds = os.getenv("GOOGLE_SHEETS_CREDS_JSON")
    else:
        json_creds = creds
    creds_dict = json.loads(json_creds)
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict)
    client = gspread.authorize(creds)
    logger.info(f"G-sheets initialized")
    return client


def open_sheet(client, sn="", wn=""):
    """Function to open a google sheet at a given worksheet"""
    sheet = client.open(sn).worksheet(wn)
    logger.info(f"Opened sheet:{sn} at worksheet:{wn}")
    return sheet


def read_data(sheet):
    """Function to read data into a pandas dataframe from the current sheet"""
    df = pd.DataFrame(sheet.get_all_records())
    logger.info(f"Data read from {sheet}")
    return df


def write_data(sheet,df):
    """Function to write a pandas dataframe to the entire current sheet (overwrites current sheet)"""
    df.fillna("",inplace=True) #fails if any NaNs
    try:
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        logger.info(f"Wrote data to {sheet}")
    except Exception as error:
        logger.error(f"Failed to write data becase {error}")


def append_data(sheet,row):
    """Function to add a row (list) to a google sheet"""    
    try:
        sheet.append_row(values=row)
        logger.info(f"Appended row to {sheet}")
    except Exception as error:
        logger.error(f"Failed to append row: {error}")


def dump_to_sheets(sheet,worksheet,sql="SELECT * FROM table"):
    """Function to dump sql view or table to sheet based on q defaults to selecting all"""
    sheet = open_sheet(init_sheets(), sheet, worksheet)
    conn = connect_to_database.get_database_connection(local_dev=local_dev)
    df = pd.read_sql_query(sql, conn)
    write_data(sheet,df)


def filter_df(df,col,word):
    """Filters out any entries that do not have word(string regex) in the columns specified (col)"""
    return df[df[col].str.contains(word,na=False)]


def combine_cols(df,cols,out):
    """Function to combine list of string cols in one col"""
    output = ''
    for col in cols:
       output += df[col].astype(str) + ' '
    df[out] = output.str.rstrip() #get rid of trailing space
    return df


