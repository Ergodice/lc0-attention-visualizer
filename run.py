from app import app
import webbrowser
from threading import Timer

def open_browser():
    webbrowser.open_new_tab("http://localhost:8050")



if __name__ == '__main__':
    #Timer(1, open_browser).start() #open browser with delay so server has time to start up
    #app.run_server(debug=True, threaded=True)#, use_reloader=False, dev_tools_hot_reload=False)
    app.run_server(debug=True, threaded=True, use_reloader=False, dev_tools_hot_reload=False)