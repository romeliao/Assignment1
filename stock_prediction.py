# File: stock_prediction.py
# Authors: Bao Vo and Cheong Koo
# Date: 14/07/2021(v1); 19/07/2021 (v2); 02/07/2024 (v3)

# Code modified from:
# Title: Predicting Stock Prices with Python
# Youtuble link: https://www.youtube.com/watch?v=PuZY9q-aKLw
# By: NeuralNine

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import pandas_datareader as web
import datetime as dt
import tensorflow as tf
import yfinance as yf
import mplfinance as mpf
import os
import time

from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, LSTM,GRU,Bidirectional,InputLayer
from ArimaModel import train_arima_model, ARIMA_ORDER,plot_predictions,print_arima_predictions

from Candlestick import plot_candlestick_chart
from Boxplot import plot_stock_boxplot
from DeepLearningModel import create_model
from multistepFunction import create_multistep_model, prepare_multistep_data, multistep_predict
from multivariateFunction import multivariate_prediction




COMPANY = 'CBA.AX'
TRAIN_START = '2021-05-02'              # Start date to read
TRAIN_END = '2023-10-09'                # End date to read
FEATURES = ['Open','High','Low','Close','Adj Close','Volume']  #list of specific columns 
NAN_STRATEGY = 'ffill'                  #varaible to handle missing data
PRICE_VALUE = "Open"                    #indicates what price column will be used as target value 
SPLIT_METHOD = 'ratio'                  #method to split the data into training and testing sets
TEST_SIZE = 0.3                         #proportion of data to be used for testing
SPLIT_DATE = '2022-01-01'               #date to split the data into training and testing sets
SCALE = 'True'                          # this is to indicate if teh feature scaling is applied to the data
FEATURE_RANGE = (0,1)                   # the range to which the features will be scaled, usually between 0 and 1
WINDOW_SIZE = 20                        # this is the number of consecutive trading days to consider for the moving window
                                        # to generate the inputs for the models 
sequence_length = 10                    # Number of time steps in the input sequence
n_features = 4                          # Number of features in each time step
units = 200                             # Number of units in the LSTM layer
n_layers = 5                            # Number of LSTM layers
dropout = 0.6                           # Dropout rate
loss = 'mean_squared_error'             # Loss function
optimizer = 'adam'                      # Optimizer
bidirectional = True                   # Whether to use Bidirectional LSTM
cell = LSTM
K = 20                                  # number of days to predict into the future 


#------------------------------------------------------------------------------
# load and process data function
#------------------------------------------------------------------------------
# This function is used to load and process stock data for a spcific company withing a specific time frame 
# This function allows handling missing values and can save the processed data to a file for future use 
def load_and_process_dataset(company, start_date, end_date, features, 
                             nan_strategy = 'ffill', file_path =None,
                             split_method="ratio", test_size=0.2,
                             split_date=None, random_state=None,
                             scale=False, feature_range=(0,1)):
    
    #this is to ensure that the start date and end date are called as objects
    #and not text.
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    #load data from a file if it exists
    # indel_col=0 is used to specifi that the first column should be use as 
    # the index of the dataframe
    # the parse_dates= ture is used to ensure that the index is parsed as dates
    #rather than string
    if file_path and os.path.exists(file_path):
        data = pd.read_csv(file_path, index_col=0, parse_dates=True)
    
        #filter data by the specified date range 
        #data is filtered to include only the rows between 'start_date' and 'end date'
        data = data[(data.index >= start_date) & (data.index <= end_date)]
    else:
        #doanload data using yfinance 
        # if there is no data file found it will download the data using yfinance
        data = yf.download(company, start=start_date, end=end_date)
        
        #Select the desired features 
        data = data [features]

        #handle missing values 
        # the foward fill is used to fill missing values by propagating the last valid 
        # value forward to the next missing value 
        if nan_strategy =="ffill":
            data.fillna(method = 'ffill', inplace = True)

        # the backwordfill is used to fill missing value by propagating the next valid
        # value backward to the previous missing value
        # its useful to fill missing vlaues with the next known value, assuming that 
        # the upcoming data should be used to estimate missing values 
        elif nan_strategy =="bfill":
            data.fillna(method = 'bfill', inplace = True)

        # the drop missing value is used to remove any rows or columns with missing values 
        # from the dataset
        elif nan_strategy =="drop":
            data.dropna(inplace = True)
        else :
            raise ValueError("Invalid NaN handling strategy. Choose from 'ffill', 'bfill', or 'drop'.")
    
    #if a file path is provided save the data
    # this code takes the file and save it to the designated file path 
        if file_path:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            data.to_csv(file_path)

    #Initializ a dictionary to store scalers if scaling is enabled 
    column_scaler = {}

    if scale:
        for column in features:
            scaler = MinMaxScaler(feature_range=feature_range)
            data[column] = scaler.fit_transform(data[column].values.reshape(-1,1))
            column_scaler[column] = scaler
    #what this function does is that its a loop that iterates each column that is 
    # specified in the features list 
    #is then creates a scaler for each feature a new MinMaxScaler is created. the feature_range will specifies
    #the range to which the data is scaled to.
    #the data is then reshaped into a 2D array with one column and multiple rows
    #the fit transform is applied to the data which scales the data and replaces the original values in the dataset 
    #The values is then sotred in the column_Scaler dictionary, this allows it to reverse the transformation later if needed

    #split the data into training and testing sets
    if split_method == 'ratio':
        train_data, test_data = train_test_split(data, test_size=test_size, shuffle=False)
    elif split_method =='date' and split_date:
        train_data = data[data.index < split_date]
        test_data = data[data.index >= split_date]
    elif split_method =='random':
        train_data, test_data = train_test_split(data, test_size=test_size, random_state= random_state)
    else:
        raise ValueError("Invalid split method. choose from 'ratio','date', or 'random'.")

    return train_data, test_data

#------------------------------------------------------------------------------
# Load Data
#------------------------------------------------------------------------------
#file path to save the data
#FILE_PATH = "data/stock_data.csv"       
date_now = time.strftime("%Y-%m-%d")

ticker_data_filename = os.path.join("csv-results", f"{COMPANY}_{date_now}.csv")
# model name to save, making it as unique as possible based on parameters
model_name = f"{date_now}_{COMPANY}-{SCALE}-{SPLIT_DATE}-{time}\
{loss}-{optimizer}-{cell.__name__}layers-{n_layers}-units-{units}"

# data = web.DataReader(COMPANY, DATA_SOURCE, TRAIN_START, TRAIN_END) # Read data using yahoo

train_data, test_data = load_and_process_dataset(COMPANY, TRAIN_START, TRAIN_END, 
                                                 FEATURES, nan_strategy=NAN_STRATEGY, 
                                                 file_path=ticker_data_filename, 
                                                 split_method=SPLIT_METHOD, 
                                                 test_size=TEST_SIZE, 
                                                 split_date=SPLIT_DATE,scale=SCALE,
                                                 feature_range=FEATURE_RANGE)


#------------------------------------------------------------------------------
# Calling ARIMA Model
#------------------------------------------------------------------------------
model_fit = train_arima_model(train_data=train_data, order=ARIMA_ORDER)

#------------------------------------------------------------------------------
# Training the Arima Model
#------------------------------------------------------------------------------                                 
#extract the target variable for ARIMA 
train_target = train_data[PRICE_VALUE]
test_target = test_data[PRICE_VALUE]

#train the ARIMA model
arima_model = train_arima_model(train_target)

# Make predictions using the ARIMA model
arima_predictions = arima_model.forecast(steps=len(test_target))
arima_predictions = arima_predictions.values


#------------------------------------------------------------------------------
# Prepare Data
#------------------------------------------------------------------------------
scaler = MinMaxScaler(feature_range=(0, 1)) 
# Note that, by default, feature_range=(0, 1). Thus, if you want a different 
# feature_range (min,max) then you'll need to specify it here
scaled_data = scaler.fit_transform(train_data[PRICE_VALUE].values.reshape(-1, 1))
# Flatten and normalise the data
# First, we reshape a 1D array(n) to 2D array(n,1)
# We have to do that because sklearn.preprocessing.fit_transform()
# requires a 2D array
# Here n == len(scaled_data)
# Then, we scale the whole array to the range (0,1)
# The parameter -1 allows (np.)reshape to figure out the array size n automatically 
# values.reshape(-1, 1) 
# https://stackoverflow.com/questions/18691084/what-does-1-mean-in-numpy-reshape'
# When reshaping an array, the new shape must contain the same number of elements 
# as the old shape, meaning the products of the two shapes' dimensions must be equal. 
# When using a -1, the dimension corresponding to the -1 will be the product of 
# the dimensions of the original array divided by the product of the dimensions 
# given to reshape so as to maintain the same number of elements.

# Number of days to look back to base the prediction
PREDICTION_DAYS = 70 # Original

# To store the training data
x_train = []
y_train = []

scaled_data = scaled_data[:,0] # Turn the 2D array back to a 1D array
# Prepare the data
for x in range(PREDICTION_DAYS, len(scaled_data)):
    x_train.append(scaled_data[x-PREDICTION_DAYS:x])
    y_train.append(scaled_data[x])

# Convert them into an array
x_train, y_train = np.array(x_train), np.array(y_train)
# Now, x_train is a 2D array(p,q) where p = len(scaled_data) - PREDICTION_DAYS
# and q = PREDICTION_DAYS; while y_train is a 1D array(p)

x_train, y_train = prepare_multistep_data(scaled_data, PREDICTION_DAYS, k=K)
x_train = np.reshape(x_train, (x_train.shape[0], x_train.shape[1], 1))
# We now reshape x_train into a 3D array(p, q, 1); Note that x_train 
# is an array of p inputs with each input being a 2D array 

#------------------------------------------------------------------------------
# Build the Model
#------------------------------------------------------------------------------
model = Sequential() # Basic neural network
# See: https://www.tensorflow.org/api_docs/python/tf/keras/Sequential
# for some useful examples

model.add(LSTM(units=50, return_sequences=True, input_shape=(x_train.shape[1], 1)))
# This is our first hidden layer which also spcifies an input layer. 
# That's why we specify the input shape for this layer; 
# i.e. the format of each training example
# The above would be equivalent to the following two lines of code:
# model.add(InputLayer(input_shape=(x_train.shape[1], 1)))
# model.add(LSTM(units=50, return_sequences=True))
# For som eadvances explanation of return_sequences:
# https://machinelearningmastery.com/return-sequences-and-return-states-for-lstms-in-keras/
# https://www.dlology.com/blog/how-to-use-return_state-or-return_sequences-in-keras/
# As explained there, for a stacked LSTM, you must set return_sequences=True 
# when stacking LSTM layers so that the next LSTM layer has a 
# three-dimensional sequence input. 

# Finally, units specifies the number of nodes in this layer.
# This is one of the parameters you want to play with to see what number
# of units will give you better prediction quality (for your problem)

model.add(Dropout(0.2))
# The Dropout layer randomly sets input units to 0 with a frequency of 
# rate (= 0.2 above) at each step during training time, which helps 
# prevent overfitting (one of the major problems of ML). 

model.add(LSTM(units=50, return_sequences=True))
# More on Stacked LSTM:
# https://machinelearningmastery.com/stacked-long-short-term-memory-networks/

model.add(Dropout(0.2))
model.add(LSTM(units=50))
model.add(Dropout(0.2))

model.add(Dense(units=1)) 
# Prediction of the next closing value of the stock price

# We compile the model by specify the parameters for the model
# See lecture Week 6 (COS30018)
model.compile(optimizer='adam', loss='mean_squared_error')
# The optimizer and loss are two important parameters when building an 
# ANN model. Choosing a different optimizer/loss can affect the prediction
# quality significantly. You should try other settings to learn; e.g.
    
# optimizer='rmsprop'/'sgd'/'adadelta'/...
# loss='mean_absolute_error'/'huber_loss'/'cosine_similarity'/...

# Now we are going to train this model with our training data 
# (x_train, y_train)
model.fit(x_train, y_train, epochs=20, batch_size=30)
# Other parameters to consider: How many rounds(epochs) are we going to 
# train our model? Typically, the more the better, but be careful about
# overfitting!
# What about batch_size? Well, again, please refer to 
# Lecture Week 6 (COS30018): If you update your model for each and every 
# input sample, then there are potentially 2 issues: 1. If you training 
# data is very big (billions of input samples) then it will take VERY long;
# 2. Each and every input can immediately makes changes to your model
# (a souce of overfitting). Thus, we do this in batches: We'll look at
# the aggreated errors/losses from a batch of, say, 32 input samples
# and update our model based on this aggregated loss.

# save the final dataframe to csv-results folder
csv_results_folder = "csv-results"
if not os.path.isdir(csv_results_folder):
    os.mkdir(csv_results_folder)
csv_filename = os.path.join(csv_results_folder, model_name + ".csv")

# TO DO:
# Save the model and reload it
# Sometimes, it takes a lot of effort to train your model (again, look at
# a training data with billions of input samples). Thus, after spending so 
# much computing power to train your model, you may want to save it so that
# in the future, when you want to make the prediction, you only need to load
# your pre-trained model and run it on the new input for which the prediction
# need to be made.



#------------------------------------------------------------------------------
# Test the model accuracy on existing data
#------------------------------------------------------------------------------
# Load the test data
TEST_START = '2021-06-20'
TEST_END = '2023-05-30'

# test_data = web.DataReader(COMPANY, DATA_SOURCE, TEST_START, TEST_END)
#test_data = yf.download(COMPANY,TEST_START,TEST_END)

train_data, test_data = load_and_process_dataset(COMPANY, TRAIN_START, TRAIN_END, 
                                                    FEATURES, nan_strategy=NAN_STRATEGY, 
                                                    file_path=ticker_data_filename, 
                                                    split_method=SPLIT_METHOD, 
                                                    test_size=TEST_SIZE, 
                                                    split_date=SPLIT_DATE, scale=SCALE,
                                                    feature_range=FEATURE_RANGE)


# The above bug is the reason for the following line of code
# test_data = test_data[1:]

actual_prices = test_data[PRICE_VALUE].values

total_dataset = pd.concat((train_data[PRICE_VALUE], test_data[PRICE_VALUE]), axis=0)

model_inputs = total_dataset[len(total_dataset) - len(test_data) - PREDICTION_DAYS:].values
# We need to do the above because to predict the closing price of the fisrt
# PREDICTION_DAYS of the test period [TEST_START, TEST_END], we'll need the 
# data from the training period

model_inputs = model_inputs.reshape(-1, 1)
# TO DO: Explain the above line

model_inputs = scaler.transform(model_inputs)
# We again normalize our closing price data to fit them into the range (0,1)
# using the same scaler used above 
# However, there may be a problem: scaler was computed on the basis of
# the Max/Min of the stock price for the period [TRAIN_START, TRAIN_END],
# but there may be a lower/higher price during the test period 
# [TEST_START, TEST_END]. That can lead to out-of-bound values (negative and
# greater than one)

#------------------------------------------------------------------------------
# Make predictions on test data
#------------------------------------------------------------------------------
x_test = []
for x in range(PREDICTION_DAYS, len(model_inputs)):
    x_test.append(model_inputs[x - PREDICTION_DAYS:x, 0])

x_test = np.array(x_test)
x_test = np.reshape(x_test, (x_test.shape[0], x_test.shape[1], 1))
# TO DO: Explain the above 5 lines

predicted_prices = model.predict(x_test)
predicted_prices = scaler.inverse_transform(predicted_prices)
# Clearly, as we transform our data into the normalized range (0,1),
# we now need to reverse this transformation 

#this line creates an ensemble of predictions by averaging two sets of predicted values
ensemble_predictions = (arima_predictions + predicted_prices.flatten()) / 2

#this is used to extract the actual prices from the test set
actual_prices = test_target.values

#------------------------------------------------------------------------------
# Plot the test predictions
#------------------------------------------------------------------------------

plt.plot(actual_prices, color="black", label=f"Actual {COMPANY} Price")
plt.plot(predicted_prices, color="green", label=f"Predicted {COMPANY} Price")
plt.title(f"{COMPANY} Share Price")
plt.xlabel("Time")
plt.ylabel(f"{COMPANY} Share Price")
plt.legend()
plt.show()

#------------------------------------------------------------------------------
# Plot the Arima Model
#------------------------------------------------------------------------------
#Calling graph function for ARIMA Model
plot_predictions(actual_prices, arima_predictions, predicted_prices, 
                 ensemble_predictions,company_name=COMPANY)


#------------------------------------------------------------------------------
# Calling Candlestick and Boxplot graphs
#------------------------------------------------------------------------------
#plot candlestick chart for the data.
#the plot_candlestick_chart is used to call the function to create the candlestick graph 
#the campany argument is used to pass the company name into the graph title 
#the train start and train end argument is used to call the data that is used to create the graphs 
#the n_days=1 is used to represent the data for the single trading days and the n_days are set to a higher number
#where each candlestick would represent the aggregated data
plot_candlestick_chart(COMPANY, TEST_START,TEST_END, n_days=1)

#plot boxplot for the data
#the plot_stock_boxplot is the function being called this function is used to
#create the box plot graph
#the train data arugment is used to represent teh stock data. this data frame wourld use columns such as 
#'Open', 'Close','High','low'
#The colum = close is the keyword argument that specifies which clumn of data shoudl be used for ploting the boxplot
#The window_SIZE is used to specify the size of the moving window used to group the data for teh boxplots 
plot_stock_boxplot(train_data,column='Close', window=WINDOW_SIZE)


#------------------------------------------------------------------------------
# Predict next day
#------------------------------------------------------------------------------
real_data = [model_inputs[len(model_inputs) - PREDICTION_DAYS:, 0]]
real_data = np.array(real_data)
real_data = np.reshape(real_data, (real_data.shape[0], real_data.shape[1], 1))

prediction = model.predict(real_data)
prediction = scaler.inverse_transform(prediction)
print(f"\nPrediction: {prediction}")



#------------------------------------------------------------------------------
# call deep learning model
#------------------------------------------------------------------------------
# Create the model using the function
model = create_model(sequence_length, n_features, units=units, cell=GRU,
                     n_layers=n_layers, dropout=dropout)


# Summary of the model to check the architecture
print("\n")
model.summary()

#------------------------------------------------------------------------------
# print ARIMA Predictions
#------------------------------------------------------------------------------
print_arima_predictions(arima_predictions)


#------------------------------------------------------------------------------
# Calling multistep model
#------------------------------------------------------------------------------
#calling multistep model
model = create_multistep_model(sequence_length=PREDICTION_DAYS, 
                               n_features=1, 
                               units=units, 
                               n_layers=n_layers, 
                               dropout=dropout, 
                               k=K)

#scaled_data[-PREDICTION_DAYS:]: This line extracts the last PREDICTION_DAYS entries from scaled_data.
#scaled_data: This is the data you previously scaled (probably containing features like 'Open', 'High', 'Low', 'Close', etc.) 
#PREDICTION_DAYS: This variable specifies how many days of data you want to use as input for your prediction.
model_inputs = scaled_data[-PREDICTION_DAYS:]  # Last 'PREDICTION_DAYS' from the scaled data

# the function is called here to make predictions using the LSTM model 
prediction = multistep_predict(model, model_inputs, PREDICTION_DAYS, k=K)

# the result of the mltistep prediction is printed out showing the forecasted values for the next 
# K days 
print(f"\nMultistep Prediction for {K} days: \n {prediction} \n")

# Plotting the results for multistep prediction to see the predicted outcome to the actual outcome
plt.figure(figsize=(14, 7))
plt.plot(y_train, label='Actual Outcomes', color='blue', linewidth=2)
plt.plot(prediction, label='Predicted Outcomes', color='red', linestyle='dashed', linewidth=2)
plt.title('Predicted vs Actual Outcomes')
plt.xlabel('Time Step')
plt.ylabel('Value')
plt.legend()
plt.show()

# calling the multivariate Prediction function
prediction = multivariate_prediction(company=COMPANY, start_date=TRAIN_START, end_date=TRAIN_END,
                                     prediction_days=PREDICTION_DAYS, features=FEATURES)
                                     
