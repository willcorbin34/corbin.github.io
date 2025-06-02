
import pandas as pd
from bs4 import BeautifulSoup
from pydantic import BaseModel, field_validator, HttpUrl
import requests
import re
from urllib.parse import urljoin
import os
import numpy as np
import time
import base64
import io
import json
import matplotlib.pyplot as plt


def extract_game_log(url):
    response = requests.get(url)
    response.raise_for_status()  
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table', {'id': 'player_game_log'})
    if table is None:
        return None
    df = pd.read_html(str(table))[0]
    return df

def transform_game_log(df, player_name, position, class_rating):
    game_log = df[['PTS', 'AST', 'TRB', 'BLK', 'ORB', 'STL']]
    game_log = game_log[game_log['PTS'] != 'PTS']
    for col in game_log.columns:
        game_log[col] = pd.to_numeric(game_log[col], errors='coerce').astype('Int64')
    game_log = game_log[game_log['PTS'] <= 60]
    game_log = game_log.reset_index(drop=True)
    resulting_df = pd.DataFrame([get_ten_highest_stats(game_log, player_name)], columns=['Player', 'PTS', 'AST', 'TRB', 'BLK', 'ORB', 'STL'])
    resulting_df['Position'] = position
    resulting_df['Class Rating'] = class_rating
    return resulting_df

def get_ten_highest_stats(df, player_name):
    stats_list = ['PTS', 'AST', 'TRB', 'BLK', 'ORB', 'STL']
    resulting_list = []
    resulting_list.append(player_name)
    for el in stats_list:
        ten_highest = df[el].sort_values(ascending=False).head(10)
        output = ten_highest.sum() / 10

        resulting_list.append(output)

    return resulting_list

def extract_player_stats(url):
    response = requests.get(url)
    response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table', {'id': 'players_per_game'})
    if table is None:
        return None
    df = pd.read_html(str(table))[0]
    return df

def transform_player_stats(df):
    shooting_splits_df = pd.DataFrame([get_shooting_splits(df)], columns=['3P%', 'FT%', '3PA'])
    return shooting_splits_df

def get_shooting_splits(df):
    season = df[df['Season'] == '2024-25']
    temp_list = []
    three_pct = df['3P%']
    ft_pct = df['FT%']
    three_att = df['3PA']
    temp_list.append(three_pct[0])
    temp_list.append(ft_pct[0])
    temp_list.append(three_att[0])
    return temp_list

def merge_player(df1, df2):
    merged_df = pd.concat([df1, df2], axis=1)
    return merged_df

def load_player_into_db(df):

    file_path = "transformed_player_db.csv"

    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            df.to_csv(file_path, mode='w', header=True, index=False)
    else:
        df.iloc[[0]].to_csv(file_path, mode='a', header=False, index=False)

def standardize_table(df):
    stats_list = ['PTS', 'AST', 'TRB', 'BLK', 'ORB', 'STL', '3P%', 'FT%', '3PA']
    for col in stats_list:
        df[col] = standardize(df[col])

    return df

def standardize(arr):
    return (arr - np.mean(arr)) / np.std(arr)

def raw_total(df):
    df['Raw Total'] = df[['PTS', 'AST', 'TRB', 'BLK', 'ORB', 'STL', '3P%', 'FT%', '3PA']].sum(axis=1)
    df['Net Raw Total'] = 5 * (1.2**df['Raw Total'])
    return df

def adjusted_total(df):
    df['Adjusted Total'] = df['Net Raw Total'] * (1.7 ** (1 - df['Class Rating']))
    return df

def scrape_player(player_name, repeat_name, position, class_rating,
                  game_log_url: str = 'https://www.sports-reference.com/cbb/players/cooper-flagg-1/gamelog/2025',
                  player_stats_url: str = 'https://www.sports-reference.com/cbb/players/cooper-flagg-1.html'):

    lower_name = player_name.lower()

    url_replaced = game_log_url.replace('cooper-flagg', lower_name)
    url_replaced = url_replaced.replace('1', str(repeat_name))
    url_replaced = url_replaced.replace(' ', '-')

    url_replaced_2 = player_stats_url.replace('cooper-flagg', lower_name)
    url_replaced_2 = url_replaced_2.replace('1', str(repeat_name))
    url_replaced_2 = url_replaced_2.replace(' ', '-')

    extracted_game_log = extract_game_log(url_replaced)
    transformed_game_log = transform_game_log(extracted_game_log, player_name, position, class_rating)

    extracted_player_stats = extract_player_stats(url_replaced_2)
    transformed_player_stats = transform_player_stats(extracted_player_stats)

    merged_player = merge_player(transformed_game_log, transformed_player_stats)

    transformed_file_result = load_player_into_db(merged_player)

    return


initial_df = pd.read_csv('draft_prospects_2025.csv')
for index,row in initial_df.iterrows():
    scrape_player(row['Player'], row['Repeat Name'], row['Position'], row['Class Rating'])
    time.sleep(5)

def run_model():
    transformed_db = pd.read_csv('transformed_player_db.csv')
    standardized_db = standardize_table(transformed_db)

    net_raw_total_df = raw_total(standardized_db).sort_values(by='Net Raw Total', ascending=False)
    net_raw_total_df.to_csv('net_raw_total_df.csv', index=False)    

    adjusted_total_df = adjusted_total(net_raw_total_df).sort_values(by='Adjusted Total', ascending=False)
    adjusted_total_df.to_csv('adjusted_total_df.csv', index=False)  
    return

run_model()


