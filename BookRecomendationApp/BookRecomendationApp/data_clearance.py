import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load the dataset. 
dataframe = pd.read_csv('books_cleaned.csv')

def clear_data(dataframe):
    '''
    This function analyzes and clears the dataset by identifying and addressing missing values, anomalies, and inconsistencies in the data.
    It performs the following steps:
    1. Removes duplicate entries.
    1. Analyzes the dataset to identify missing values in each column.
    2. Identifies anomalies in numerical data columns by checking for outliers or unexpected values.
    3. Identifies anomalies in categorical data columns by checking for inconsistent naming conventions or unexpected categories.
    4. Cleans the data by:
       - Standardizing naming conventions in categorical columns.
       - Removing redundant columns.
       - Converting data formats to ensure consistency (e.g., date formats).
    5. Returns the cleaned dataset for further analysis.
    6. Prints out the steps taken for data clearing.
    
    '''

    dataframe = dataframe.copy()  # Work on a copy to avoid modifying original DataFrame

    # Analyze and prepare dataset for clearing
    print("Initial Data Overview:")
    dataframe.info()
    dataframe.describe()
    dataframe.head()

    # Remove duplicates
    dataframe = dataframe.drop_duplicates()

     # Check for missing values
    print("\nMissing Values in Each Column:")
    print(dataframe.isnull().sum())

    # Check for anomalies in numerical data columns
    print("\nAnomalies in Numerical Columns:")
    max_entries = dataframe.select_dtypes(include=[np.number]).max()
    min_entries = dataframe.select_dtypes(include=[np.number]).min()
    print("Max Values:\n", max_entries)
    print("Min Values:\n", min_entries)

    # Check for anomalies in categorical data columns
    print("\nAnomalies in Categorical Columns:")
    for col in dataframe.select_dtypes(include=['object']).columns:
        unique_values = dataframe[col].unique()
        print(f"Column '{col}' Unique Values:\n", unique_values)

    # Data clearing steps
    # 1. 

     # Handle missing values
    #dataframe = dataframe.dropna(subset=['title', 'author', 'rating'])

    # Convert data types
    #dataframe['rating'] = pd.to_numeric(dataframe['rating'], errors='coerce')
    #dataframe = dataframe.dropna(subset=['rating'])

    # Remove outliers in ratings (assuming ratings are between 0 and 5)
    #dataframe = dataframe[(dataframe['rating'] >= 0) & (dataframe['rating'] <= 5)]

    return dataframe

# Clear the data
cleaned_dataframe = clear_data(dataframe)