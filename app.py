# Main webapp file, holds all rendering of templates and execution of webpage main
from datetime import datetime
from flask import Flask, redirect, render_template, request, session, url_for
from PIL import Image
import base64
import io
import os
import utils


app = Flask(__name__)


# View function and endpoint for home page
# loads main index page, which allows for selection of Stock to view
# Inputs: None
# Outputs: A HTML page (index.html)
@app.route("/")
@app.route("/index")
@app.route("/home")
def home():
    # Check if previously viewed a stock via Session
    if "index" in session:
        # if so, remove it to allow for smooth view of next stock
        session.pop("index", None)
        # Check if session has an error messages
    if "error" in session:
        # set error message and remove it from session
        error_msg = session.pop('error', None)
    else:
        # set error message to empty string if no errors
        error_msg = ""
    # get a list of all unique stock indexes for selection
    results = utils.get_unique_stocks()
    # load index page along with unique stocks passed to the page for usage and error messages
    return render_template('index.html', error=error_msg, unique=results)


# View function and endpoint for visualizing plot page
# loads main plot page based on selected stock index
# Inputs: None
# Outputs: A HTML page (plot.html) or redirect to home
@app.route("/action/visualize", methods=["POST", "GET"])
def visualize():
    # Check if a stock has been selected, via HTML form or by Session variable
    if 'index' in request.form or session.get("index"):
        # if via HTML form, update session to contain currently viewed stock
        if 'index' in request.form:
            # updating session
            session["index"] = request.form["index"]

        # Get stock data from DB
        data = utils.get_stock_data(session["index"])
        # Produce plot based on data, only using existing data
        utils.produce_plot(data[2], data[1], data[0], session["index"], pred=False)

        # Open the produced plot
        im = Image.open('fig.png')
        # create a Bytes Input/Output
        img = io.BytesIO()
        # Save the bytes of the plot image
        im.save(img, "png")
        # Encode image bytes for usage on front end
        encoded_img_data = base64.b64encode(img.getvalue())
        # Check if session has an error messages
        if "error" in session:
            # set error message and remove it from session
            error_msg = session.pop('error', None)
        else:
            # set error message to empty string if no errors
            error_msg = ""
        # Render plot template along with stock index as text, encoded image data and any error messages
        return render_template("plot.html", error=error_msg, text=f"- {session['index']}", img=encoded_img_data.decode('utf-8'))
    else:
        # if empty, set an error message to choose a stock
        session['error'] = 'Please choose a stock to view!'
        # Redirect to home endpoint
        return redirect(url_for("home"))


# View function and endpoint for visualization of predictions
# loads main plot page based on selected stock index, date and ML estimates of future
# Inputs: None
# Outputs: A HTML page (plot.html) or redirect to standard visualized plot
@app.route("/action/project", methods=["POST", "GET"])
def project():
    # Check if date has been selected for prediction of stock data
    if "project" in request.form and request.form["project"] != "":
        # Get the stock data via index in Session
        data = utils.get_stock_data(session["index"])
        # Produce a datetime object of the projection date
        end_date = datetime.strptime(request.form["project"], '%Y-%m-%d')
        # Check if date is valid to predict
        if end_date < data[3][len(data)-1]:
            # if it is not, put an error message into session
            session["error"] = "The date you projected to was not in the future!\nPlease enter a valid date!"
            # redirect to visualize
            return redirect(url_for('visualize'))
        # Produce estimates for the projections via ML
        x_proj, y_proj, proj_dates = utils.produce_projection(data, end_date)
        # Produce plot with existing and estimated data
        utils.produce_plot(data[2], data[1], data[0], session["index"], pred=True, x2=x_proj, y2=y_proj, date2=proj_dates, date=end_date)

        # Open the produced plot
        im = Image.open('fig.png')
        # create a Bytes Input/Output
        img = io.BytesIO()
        # Save the bytes of the plot image
        im.save(img, "png")
        # Encode image bytes for usage on front end
        encoded_img_data = base64.b64encode(img.getvalue())
        # Render plot template along with encoded image data
        text = f"- {session['index']} (Projected to {str(end_date)[0:10]})"
        return render_template("plot.html", text=text, img=encoded_img_data.decode('utf-8'))
    else:
        # set error message
        session['error'] = "No date was given! Please enter a valid date to predict!"
        # Redirect to visualize
        return redirect(url_for("visualize"))


# View function and endpoint for return to home action
# redirects to home page
# Inputs: None
# Outputs: redirect to home
@app.route("/action/go_home", methods=["POST", "GET"])
def go_home():
    # Redirect to home
    return redirect(url_for("home"))


# main entrypoint to webapp
if __name__ == "__main__":
    app.secret_key = os.urandom(12)
    # Populate database from included csv file
    utils.make_database('indexData.csv')
    app.run(debug=True)
