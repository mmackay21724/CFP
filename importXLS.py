import xlrd
import mysql.connector
cnx     = mysql.connector.connect(user='root', host = '10.10.30.130', password="peaceD00d", database='cfp', port = '3306', use_pure = True)
cursor  = cnx.cursor(dictionary=True)
c_many  = cnx.cursor(prepared=True)

def _getDbFields(schema, table):
    query = "SELECT COLUMN_NAME FROM information_schema.columns where table_schema = '{_schema}' and table_name = '{_table}'".format(_schema = schema, _table = table)
    cursor.execute(query)
    d = cursor.fetchall()
    ret = {}
    for i,v  in enumerate(d):
        ret[v["COLUMN_NAME"]] = ''
    return ret

def _importXLS(fileName):
    workbook = xlrd.open_workbook(fileName, on_demand = True)
    worksheet = workbook.sheet_by_index(0)
    first_row = [] # The row where we stock the name of the column
    for col in range(worksheet.ncols):
        first_row.append( worksheet.cell_value(0,col) )
    # transform the workbook to a list of dictionaries
    data =[]
    for row in range(1, worksheet.nrows):
        elm = {}
        for col in range(worksheet.ncols):
            elm[first_row[col]]=worksheet.cell_value(row,col)
        data.append(elm)
    return data


#file = input("Enter Filename")
file = "cfp.xlsx"

data        = _importXLS(file)
dbFields    = _getDbFields("cfp", "cfp_data")
#print (dbFields)
sqlInsertFields = ["CFP_Speaker", "CFP_Speaker_email", "CFP_Session_submitter"]
sqlInsertValues = []
sqlUpdate = ["CFP_Speaker = VALUES(CFP_Speaker)",
             "CFP_Speaker_email = VALUES(CFP_Speaker_email)",
             "CFP_Session_submitter = VALUES(CFP_Session_submitter)"
             ]
paramterStr = ['%s', '%s', '%s']

for idx, val in enumerate(data):

    if ("CFP_Session_ID" not in val) or (val["CFP_Session_ID"] == ''):# or ("CFP_Event_name" not in val) or (val["CFP_Event_name"] == ''):
        #print (str(idx) )
        exit(str(idx) + "  -->  " + str(val) )
    #print (str(idx) + "..." + str(val))
    temp = []
    _grpParticipants = val["CFP_Grp_participants"].split(";" )
    speakers = []
    speaker_email = []
    session_sub = []

    for grpIdx, grpVal in enumerate(_grpParticipants):
        #print(grpVal)
        if grpVal.find("(Speaker)") != -1:
            speakers.append(grpVal.split(',')[0].strip())
            speaker_email.append(grpVal.split(',')[1].strip())

        if grpVal.find(" (Session Submitter)") != -1:
            session_sub.append(grpVal.split(',')[0].strip())
            #speaker_email.append(grpVal.split(',')[1].strip())

    temp.append(", ".join(speakers))
    temp.append(", ".join(speaker_email))
    temp.append(", ".join(session_sub))
    #print (speaker_email + "..." + str(len(speaker_email)))

    for i, v in enumerate(val):
        #print ("i = " + str(i) + "   v=" + v + "    Value = " + str(val[v]))
        if v in dbFields :
            temp.append(val[v])
            #print (val[v])
            #exit(val)
            if idx == 0 :
                sqlInsertFields.append(v)
                paramterStr.append('%s')
                sqlUpdate.append("{_field} = VALUES({_field}) ".format(_field = v))

    sqlInsertValues.append(tuple(temp))
sql = ('INSERT INTO cfp_data ({_insertFields}) VALUES ({_insertValues}) ON DUPLICATE KEY UPDATE {_update}'.format
           (_insertFields = ", ".join(sqlInsertFields), _insertValues = ", ".join(paramterStr), _update = ", ".join(sqlUpdate)))

#print (sqlInsertValues)
print (sql)

result  = c_many.executemany(sql, tuple(sqlInsertValues))
print (result)
cnx.commit()

