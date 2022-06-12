# util file containing all processing functions necessary to produce data and visuals on webapp

import pandas as pd
import numpy as np
import sqlite3 as sl
import matplotlib.pyplot as plt
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from datetime import timedelta

db = "finalProject.db"


# function to take data from csv and then construct and populate a sqlite database, Called once at app start
# Inputs: 1 - String fn: filename to csv containing data
# Outputs: None
def make_database(fn):
    # Read csv via pandas and get rid of Nans
    df = pd.read_csv(fn)
    df = df.dropna()

    # Make connection and cursor via sqlite
    conn = sl.connect(db)
    curs = conn.cursor()

    # statement to remove table if already exists and then to create the new table with columns from dataframe
    stmt1 = "DROP TABLE IF EXISTS stock_data"
    stmt2 = "CREATE TABLE stock_data(ind VARCHAR(15), date DATE, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, adj_close DOUBLE)"

    # execute the statements
    curs.execute(stmt1)
    curs.execute(stmt2)

    # Insert every row of DF into the database
    df.apply(insert_row, axis=1, curs=curs)

    # Commit above insert of df to the Database
    conn.commit()
    # Close connection
    conn.close()


# helper function for usage in make_database(), inserts a row from a dataframe into the DB
# Inputs: 2 - Pandas row: contains single row of data to be inserted into database
#           - curs: sqlite cursor object to insert the row with
# Outputs: List - unique stocks in tuple each
def insert_row(row, curs=None):
    # Prepare variables for insert based on row
    v = (row['Index'], row['Date'], row['Open'], row['High'], row['Low'], row['Close'], row['Adj Close'])
    # Prepare statement for execution
    stmt = "INSERT INTO stock_data VALUES (?,?,?,?,?,?,?)"
    # Use inputted cursor to execute statements + variables
    curs.execute(stmt, v)
    # No closing or commit since this is just a helper function, will be executed >1000x times


# Database function to get list of unique stocks
# Inputs: None
# Outputs: List - unique stocks in tuple each
def get_unique_stocks():
    # Create connection to database and cursor
    conn = sl.connect(db)
    curs = conn.cursor()

    # Statement to get all unique stock indexes
    stmt = "SELECT DISTINCT ind FROM stock_data"

    # Execute Statement
    data = curs.execute(stmt)
    # get entire dataset from cursor
    results = data.fetchall()
    # Close connection
    conn.close()
    # Return results
    return results


# Database function to filter by stock index and produce average prices per date
# Inputs: 1 - String ind: stock index
# Outputs: 1 - dataframe containing stock data, dates and average prices
def get_stock_data(ind):
    # Create connection to database and cursor
    conn = sl.connect(db)
    curs = conn.cursor()

    # Preparing variables for statements
    # stock index
    v = (ind,)
    # Statement to get all date and average out price data and return as new column, filtered by stock index
    stmt = "SELECT date, (open + close + high + low + adj_close)/5 as mean FROM stock_data WHERE ind=? ORDER BY date"
    # Execute statements with respective variables
    data = curs.execute(stmt, v)

    # Turn statement output into pandas dataframe for processing
    results = pd.DataFrame(data.fetchall())
    # Parse date column from strings into datetime objects
    results[3] = pd.to_datetime(results[0], format='%Y-%m-%d')
    # Create ordinal column, scaled down to starting date of data
    results[2] = results[3].apply(convert_dates, start_date=results[3][0])
    # Remove any resulting NaNs
    results = results.dropna()

    # close connection
    conn.close()
    # Return results
    return results


# Create plot of dates and stock data, and possible with projections, and save them for display
# Inputs: 9 - List x1: Containing ordinal data for x-coords
#           - List y1: Containing stock price data for y-coords
#           - List date1: String versions of dates used on x-axis
#           - String index: Stock index being plotted
#           - List x2: Containing projected ordinal data for x-coords (optional)
#           - List y2: Containing projected stock price data for y-coords (optional)
#           - List date2: containing string versions of projected ordinal dates (optional)
#           - Boolean pred: whether to plot projected values or not (default: false)
#           - datetime date: what date the projection goes to (optional)
# Output: None
def produce_plot(x1, y1, date1, index, x2=None, y2=None, date2=None, pred=False, date=None):
    # Separate fig and ax from plt for ease of modification of axis and labels etc
    fig, ax = plt.subplots(1, 1)
    # Plot x1 and y1 as a blue-line labelled Current Data
    ax.plot(x1, y1, color="blue", label="Current Data")
    # Check if also plotting a projection of data
    if pred:
        # if so, plot the given data (x2, y2) as an orange line labelled "Projection"
        ax.plot(x2, y2, color="orange", label="Projection")
    # Make a string for title, depending on whether projection is being plotted or not
    title = f"Price of {index} Stock over Time (Projected to {str(date)[0:10]})" if pred else f"Price of {index} Stock over Time"
    # Set the x-axis label and y-axis label and title
    ax.set(xlabel='Date Observed (Year)', ylabel=f'Average Price of {index}', title=title)
    # Setting x-axis tick marks
    # Combine the list of dates if projection was plotted
    dates = list(date1) if date2 is None else list(date1)+date2
    # Leave one empty tick for the far left
    x_tick_labels = [""]
    # step through dates, getting 10 equidistant dates
    for i in range(0, len(dates), int(len(dates)/10)):
        # slice the string to get only year for brevity, and append to x_tick_labels
        x_tick_labels.append(dates[i][0:4])
    # get the min and max of the x-axis
    min_tick, max_tick = ax.get_xlim()
    # set the tick marks and distances to be equidistant based on number of elements in x_tick_labels
    ax.set_xticks(np.arange(min_tick, max_tick, step=(max_tick - min_tick) / len(x_tick_labels)))
    # Set the labels of the tick marks
    ax.set_xticklabels(x_tick_labels)
    # Create a legend for the plot
    plt.legend()
    # Save the plot as 'fig.png' and use a tightened the layout
    plt.savefig('fig.png', bbox_inches='tight')


# Using data and polynomial regression, produce predictions on stock market price up to a certain date
# Inputs: 2 - Dataframe data: contains 4 columns - string dates, ordinal dates, stock prices, datetime dates
#           - Datetime end_date: date to make stock price predictions to
# Output: 3 - List ordinals: contains ordinal for of all date predictions
#           - List y_proj: contains stock market predictions for up to end_date
#           - List dates: contains datetime object versions of ordinals
def produce_projection(data, end_date):
    # Create a sklearn pipeline to 1) create polynomial features out of the single ordinal feature,
    #                              2) use Ridge to perform least squares minimization and predict outputs
    poly_reg = make_pipeline(PolynomialFeatures(3), Ridge())
    # Reshape pandas columns for usage in model training
    arr = np.array(data[2])
    arr = arr.reshape(-1, 1)
    # Train the pipeline using existing data
    poly_reg.fit(arr, data[1])

    # produce extended dates up to end_date for prediction
    # set beginning of the date range
    start_date = data[3][len(data) - 1]
    # Create all dates within the range of start_date and end_date
    x_proj = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
    # Convert range to ordinals for inputting into pipeline
    ordinals = np.array(pd.DataFrame(x_proj)[0].apply(convert_dates, start_date=data[3][0])).reshape(-1, 1)

    # Predict outputs via trained model
    y_proj = poly_reg.predict(ordinals)
    # Convert date range to strings for plotting
    dates = [str(x)[0:10] for x in x_proj]
    # Return ordinals, predictions, and string dates
    return ordinals, y_proj, dates


# Helper function to turn dates into ordinals based on a start date, for use in Pandas apply()
# Inputs: 2 - Datetime current_date: date to be turned into ordinal
#           - Datetime start_date: 'zero' date for comparison, if converted would return 0 (kwarg for use in pandas)
# Output: Int - Number of days between current_date and start_date
def convert_dates(current_date, start_date=None):
    # Calculate and return number of days between current_date and start_date
    return (current_date - start_date).days
