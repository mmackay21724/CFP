_author__ = 'Mike'


from flask import Flask,  Request, jsonify, request
from flask_restful import reqparse, abort, Api, Resource
import socket
import mysql.connector
import xlrd
import os

USERNAME = os.environ["MYSQL_USER"]
PASSWORD = os.environ['MYSQL_PASS']

cnx     = mysql.connector.connect(user=USERNAME, password=PASSWORD, database='cfp', host= '10.10.30.130', port = '3306', use_pure = True)
cnx.autocommit = True
cursor  = cnx.cursor(dictionary=True)
c_many  = cnx.cursor(prepared=True)

app = Flask(__name__)
api = Api(app)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

HOST = get_ip()
PORT = 5000
#HOST = '127.0.0.1'

def _getEventInfo(event_id):
    q = ''
    if event_id != 'all':
        q = " and event_id = '{_id}'".format(_id=event_id)

    query = ("select * from events where status != 'closed'" + q)
    cursor.execute(query)
    data = cursor.fetchall()
    for idx, val in enumerate(data):
        sql = "select * from event_resources where event_id = '{_id}'".format(_id=val["event_id"])
        cursor.execute(sql)
        d = cursor.fetchall()
        # print (d)
        data[idx]["resources"] = d
    # print (data)
    return (data)

def _getDataFields():
    query = ("select * from data_fields where active = 'yes' ")
    cursor.execute(query)
    return cursor.fetchall()

def _importXLS(fileName):
    workbook = xlrd.open_workbook(fileName, on_demand=True)
    worksheet = workbook.sheet_by_index(0)
    first_row = []  # The row where we stock the name of the column
    for col in range(worksheet.ncols):
        first_row.append(worksheet.cell_value(0, col))
    # transform the workbook to a list of dictionaries
    data = []
    for row in range(1, worksheet.nrows):
        elm = {}
        for col in range(worksheet.ncols):
            elm[first_row[col]] = worksheet.cell_value(row, col)
        data.append(elm)
    return data


# -----
#  TESTED AND GOOD
# -------

class CFP_data(Resource):

    def __init__(self):
        pass

    def get(self, event_id):
        return (self._getCfpData(event_id)), 201

    def post(self):
        self.content = request.get_json()
        return self._genSQL()

    def _genSQL(self):
        dataFields = _getDataFields()
        editableFields = self._generateEditableDict(dataFields)
        # print (dataFields)
        for recordIdx, recordVal in enumerate(self.content):
            updateFields = []
            temp = []
            id = ''
            if "CFP_Session_ID" not in recordVal:
                return "Missing primary key", 422
            for k, v in recordVal.items():
                #print (str(k) + "..." + v )
                if k == "CFP_Session_ID":
                    id = v
                elif k in editableFields and editableFields[k] == 'true':
                    updateFields.append("{_field} = %s ".format(_field = k))
                    temp.append(v)
            temp.append(id)
            updateValues = tuple(temp)
            if len(updateFields) > 0 :
                sql ="UPDATE cfp_data SET {_fields} WHERE CFP_session_ID = %s".format(_fields = ", ".join(updateFields))
                #print(sql)
                #print (updateValues)
                cursor.execute(sql, updateValues)
                auditSql  = "INSERT INTO audit ('data', 'sql', 'userid') VALUES (%s, %s, %s)"
                auditData = (updateValues, sql, "system")
#                cursor.execute(auditSql,  auditData)

                cnx.commit()
                print("affected rows = {}".format(cursor.rowcount))

        return (len(self.content))

    def _getCfpData(self, event_id):
        #
        # #    For this whole thing to work there needs to be a 1:1 mapping of the fields in CFP_DATA to DATA_FIELDS.
        #
        data = _getDataFields()
        #print (data)
        cfpSchema = {"columns": [], "data": []}

        # Start by building the columns data - at the same time build a list that can be iterated thru to make sure we provide data in the same order...
        dataFields = {"label": [], "type": []}

        for d in data:
            #print ("d==>" + str(d))
            temp = {"name": d["label"],
                    "fieldName" : d["field_name"],
                    "cellType": d["cell_type"],
                    "options": {"display_grid": d["display_grid"], "display_detail": d["display_detail"], "editable": d["editable"]}
                 }
            dataFields["label"].append(d["field_name"])  # create a master ordered list of fields and use this to build the data...
            dataFields["type"].append(d["cell_type"])  # create a master ordered list of fields and use this to build the data...

            #print (temp)
            #print (d["field_name"])
            # If there are default values (aka dropdowns) then grab them
            if d["cell_type"] == 'selectField' :
                q =''
                defData = []
                if d["def_source"] == 'event_resources':
                    q = "select resource_name as label from event_resources where event_id = 1"
                else :
                    q = "select label from lookups where type = '{fn}'".format(fn=d["field_name"])

                cursor.execute(q)
                d2 = cursor.fetchall()
                for defs in d2 :
                    defData.append(defs["label"])
                    temp["defaultValues"] = defData
            cfpSchema["columns"].append(temp)


            #temp[d]print(d["field_name"])
        #print (cfpSchema)

        #cfpDataQuery = "select {df} from cfp_all_data where event_id ={eventID} and CFP_session_code = '1120' ".format(df=(",".join(dataFields["label"])), eventID="1")
        #print ( ",".join(dataFields["label"]) )
        cfpDataQuery = "select {df} from cfp_data where event_id ={eventID} ".format(df=(",".join(dataFields["label"])), eventID=event_id)

        #print (cfpDataQuery)
        cursor.execute(cfpDataQuery)
        cfpData = cursor.fetchall()


        for cfpD in cfpData:
            #print (dataFields["label"])
            #print ("SESSION_CODE -- " + cfpD["CFP_session_code"])
            #exit()
            #print (cfpD)
            zList = []

            for idx, val in enumerate(dataFields["label"]):
            #for i in range(len(dataFields["label"])):
                z = {}
                if cfpD[val] == None:
                    cfpD[val] = ''
                #print ("idx -->" + str(idx) + "   VAL -- " + val + "cfpD[val] -- " + cfpD[val] )
                #print (dataFields["label"][i] + "--" + dataFields["type"][i])

                z["value"]      = cfpD[val]
                z["cellType"]   = dataFields["type"][idx]
                z["fieldName"]  = (dataFields["label"][idx])
                zList.append(z)
                #print (z)
                #exit()
            cfpSchema["data"].append(zList)

        #print (cfpSchema)
        return cfpSchema

    def _generateEditableDict (self, d):
        retDict = {}
        for i, v in enumerate(d):
            retDict.update ( {v["field_name"] : v["editable"]})
        #print  (retDict)
        return retDict

class Data_Import(Resource):

    def __init__(self):
        pass

    def post(self):
        self.content = request.get_json()
        #file = "CFP_Data/cfp2.xlsx"
        #data = _importXLS(file)
        #print (self.content)
        self._loadData(self.content)

    def _loadData(self, data):
        dbFields = self._getDbFields("cfp", "cfp_data")
        sqlInsertFields = ["CFP_Speaker", "CFP_Speaker_email", "CFP_Session_submitter"]
        sqlInsertValues = []
        sqlUpdate = ["CFP_Speaker = VALUES(CFP_Speaker)",
                     "CFP_Speaker_email = VALUES(CFP_Speaker_email)",
                     "CFP_Session_submitter = VALUES(CFP_Session_submitter)"
                     ]
        paramterStr = ['%s', '%s', '%s']

        for idx, val in enumerate(data):

            if (("CFP_Session_ID" not in val) or (val["CFP_Session_ID"] == '') or ("CFP_Event_name" not in val) or (
                        val["CFP_Event_name"] == '')):
                print (str(idx))
                # exit(str(idx) + "  -->  " + str(val) )
            # print (str(idx) + "..." + str(val))
            else:
                temp = []
                _grpParticipants = val["CFP_Grp_participants"].split(";")
                speakers = []
                speaker_email = []
                session_sub = []

                for grpIdx, grpVal in enumerate(_grpParticipants):
                    # print(grpVal)
                    if grpVal.find("(Speaker)") != -1:
                        speakers.append(grpVal.split(',')[0].strip())
                        speaker_email.append(grpVal.split(',')[1].strip())

                    if grpVal.find(" (Session Submitter)") != -1:
                        session_sub.append(grpVal.split(',')[0].strip())
                        # speaker_email.append(grpVal.split(',')[1].strip())
                temp.append(", ".join(speakers))
                temp.append(", ".join(speaker_email))
                temp.append(", ".join(session_sub))
                # print (speaker_email + "..." + str(len(speaker_email)))

                for i, v in enumerate(val):
                    # print ("i = " + str(i) + "   v=" + v + "    Value = " + str(val[v]))
                    if v in dbFields:
                        temp.append(val[v])
                        # print (val[v])
                        # exit(val)
                        if idx == 0:
                            sqlInsertFields.append(v)
                            paramterStr.append('%s')
                            sqlUpdate.append("{_field} = VALUES({_field}) ".format(_field=v))

                sqlInsertValues.append(tuple(temp))
        sql = (
        'INSERT INTO cfp_data ({_insertFields}) VALUES ({_insertValues}) ON DUPLICATE KEY UPDATE {_update}'.format
        (_insertFields=", ".join(sqlInsertFields), _insertValues=", ".join(paramterStr), _update=", ".join(sqlUpdate)))

        # print (sqlInsertValues)
        # print (sql)
        eventSQL = "update cfp_data  c set event_id = (select event_id from events e where e.event_name = c.CFP_Event_name)"

        result = c_many.executemany(sql, tuple(sqlInsertValues))
        cursor.execute(eventSQL)
        print (result)
        cnx.commit()

    def _getDbFields(self, schema, table):
        query = "SELECT COLUMN_NAME FROM information_schema.columns where table_schema = '{_schema}' and table_name = '{_table}'".format(
            _schema=schema, _table=table)
        cursor.execute(query)
        d = cursor.fetchall()
        ret = {}
        for i, v in enumerate(d):
            ret[v["COLUMN_NAME"]] = ''
        return ret

class Events(Resource):

    def __init__(self):
        pass

    def get(self, event_id = 'all'):
        return (_getEventInfo(event_id)), 201

    def put(self):
        self.content = request.get_json()
        # Insert new record into the Events Table - get new ID
        sql =  "insert into events (ett_id, rainfocus_api, event_name,status ) VALUES ('{_id}', '{_api}', '{_name}', '{_status}')".format(_id=self.content["event"]["ett_id"],_api=self.content["event"]["rainfocus_api"], _name=self.content["event"]["event_name"], _status=self.content["event"]["status"])
        #print (sql)
        cursor.execute(sql)
        cnx.commit()
        _new_event_id = cursor.lastrowid
        print (_new_event_id)
        # Now add the resources:
        if (self.content["resources"])  and (len(self.content["resources"]) > 0):
            for k in self.content["resources"]:
                #print ( "k-->" + str(k))
                v = (_new_event_id, k["resource_name"],  k["resource_type"], k["session_count"], k["capacity"])
                sql = "insert into event_resources (event_id, resource_name, resource_type, session_count, capacity ) VALUES (%s,%s,%s,%s,%s )"
                #print (sql, v)
                cursor.execute(sql, v)
                cnx.commit()
        return (_getEventInfo(_new_event_id)), 201

    def post(self, event_id):
        self.content = request.get_json()
        #print (self.content)
        updateValues = (self.content["ett_id"], self.content["rainfocus_api"],self.content["event_name"],self.content["status"], event_id)
        sql = "UPDATE events SET ett_id = %s, rainfocus_api = %s, event_name =%s,status = %s WHERE event_id = %s"
        cursor.execute(sql, updateValues)
        cnx.commit()
        # Now add the resources:
        updateValues = []
        if (self.content["resources"])  and (len(self.content["resources"]) > 0):
            sql = "UPDATE event_resources SET resource_name = %s, resource_type = %s, session_count = %s, capacity= %s WHERE event_id= %s"
            for k in self.content["resources"]:
                print ( "k-->" + str(k))
                a = (k["resource_name"],  k["resource_type"], k["session_count"], k["capacity"],event_id)
                updateValues.append(a)
                print (sql, updateValues )
        c_many.executemany(sql, tuple(updateValues))
        cnx.commit()
        return (_getEventInfo(event_id)), 201

class Lookups(Resource):
    def __init__(self):
        # self.content = request.get_json()
        # print (self.content)
        pass

    def call(self):
        return "done"

    def get(self, type='all'):
        query = ("select * from lookups ")

        if type != 'all':
            query = query + " WHERE type = '{_type}'".format(_type=type)
        cursor.execute(query)
        return cursor.fetchall(), 201



#######     ------------
#######     ROUTES
#######     ------------

api.add_resource(CFP_data,      '/api/ver1/cfpdata/<event_id>', '/api/ver1/cfpdata')   # GET   - pulls the data for a specific event.  PUT = inserts.  POST UPDATES.
api.add_resource(Data_Import,   '/api/ver1/cfpdata/import')                             # POST.  Takes data from XLS file and merhges into the CFP_DATA table
api.add_resource(Events,        '/api/ver1/events/')                                    # GET   - a specific event details.   PUT a new record.  This also includes the resources for the event
api.add_resource(Lookups,       '/api/ver1/lookups', '/api/ver1/lookups/<type>' )       # GET  - Gets a list of all the dropdowns...

if __name__ == '__main__':
    app.run(debug=True,  host=HOST, port=PORT)
    print ("Running on host:" + HOST + "Port : " + PORT)

httpCodes = {
"200":  "OK - every this worked",
"201" : "OK - New resource has been created",
"204" : "OK - The resource was successfully deleted",
"304" : "Not Modified - The client can use cached data",
"400" : "Bad Request -  The request was invalid or cannot be served. The exact error should be explained in the error payload. E.g. The JSON is not valid",
"401" : "Unauthorized - The request requires an user authentication",
"403" : "Forbidden - The server understood the request, but is refusing it or the access is not allowed.",
"404" : "Not found - There is no resource behind the URI.",
"422" : "Unprocessable Entity - Should be used if the server cannot process the enitity, e.g. if an image cannot be formatted or mandatory fields are missing in the payload.",
"500" : "Internal Server Error - API developers should avoid this error. If an error occurs in the global catch blog, the stracktrace should be logged and not returned as response.",
}



