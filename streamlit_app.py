import copy
import datetime
from datetime import datetime
from datetime import timedelta
import altair as alt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import gsheet
from streamlit import caching
import cufflinks as cf

LOCAL = False
if LOCAL:
    cf.go_offline()

#See gsheet for fetching local creds
def st_config():
    """Configure Streamlit view option and read in credential f
ile if needed check if user and password are correct"""
    st.set_page_config(layout="wide")
    pw = st.sidebar.text_input("Enter password:")
    if pw == st.secrets["PASSWORD"]: #CHANGE CHANGE CHANGE BEFORE PUSHING!
        return st.secrets["GSHEETS_KEY"]
    else:
        return None


@st.cache
def read_data(creds,ws,gs):
    """Read court tracking data in and drop duplicate case numbers"""
    try:
        df = gsheet.read_data(gsheet.open_sheet(gsheet.init_sheets(creds),ws,gs))
    #    df.drop_duplicates("Case Number",inplace=True) #Do we want to drop duplicates???
        return df
    except Exception as e:
        return None

def convert(x):
    try:
        return x.date()
    except:
        return None

def convert_date(df,col):
    """Helper function to convert a col to a date"""
    df[col] = pd.to_datetime(df[col]).apply(lambda x: convert(x))
    return df


def agg_checklist(df_r):
    """Aggegrates a dataframe with multi indexes (but one level) seperated by a ', ' into a data frame with single indexes"""
    df_r["result"]=df_r.index
    df_b = pd.concat([pd.Series(row['count'], row['result'].split(', ')) for _,row in df_r.iterrows()]).reset_index().groupby("index").sum()
    df_a = pd.concat([pd.Series(row['cases'], row['result'].split(', ')) for _,row in df_r.iterrows()]).reset_index().groupby("index").agg(lambda x: ", ".join(x))
    df_r = df_b.merge(df_a,right_index=True,left_index=True)
    return df_r


def agg_cases(df,col,i,pie=False):
    """Aggregates a df by col and aggregates case numbers into new column seperated by ',' or <br> depending on pie flag """
    df_r = df.groupby([col,"Case Number"]).count().iloc[:,i]
    df_r.name = "count"
    df_r = pd.DataFrame(df_r)
    df_a = pd.DataFrame(df_r.to_records())
    df_r = df_r.groupby(level=0).sum()
    if pie:
        df_r["cases"] = df_a.groupby(col)["Case Number"].agg(lambda x: ',<br>'.join(x))
    else:
        df_r["cases"] = df_a.groupby(col)["Case Number"].agg(lambda x: ','.join(x))
    return df_r


def volunteer_details(cl):
    """Compute and Render Volunteer Information section"""
    df = agg_cases(cl,"Caller Name",0,True)
    #total minutes on phone per caller
    df1 = cl.groupby("Caller Name")["Length Call (minutes)"].sum()
    #Calls over time 
    df2 = agg_cases(cl,"Date Contact Made or Attempted",0,True)
      
    #calls made per tracker
    with st.beta_expander("Volunteer Information"):
        cols = st.beta_columns([1,1])
        fig = px.pie(df, values='count', names=df.index, title='Volunteer Call Count',hover_data=["cases"])
        fig.update_traces(textinfo='value')
        cols[0].plotly_chart(fig)
        fig1 = px.pie(df1, values='Length Call (minutes)', names=df1.index, title='Volunteer Call Time',hover_data=["Length Call (minutes)"])
        fig1.update_traces(textinfo='value')
        cols[1].plotly_chart(fig1)
       
        st.markdown("#### Calls over time")
        fig = go.Figure(data=go.Scatter(x=df2.index, y=df2["count"])) 
        st.plotly_chart(fig,height=200,use_container_width = True)        
 
        cols = st.beta_columns([1,1,1,5])
        cols[0].markdown("**Name**")
        cols[1].markdown("**Call Count**")
        cols[2].markdown("**Time on Calls**")
        cols[3].markdown("**Case Numbers**")
        for i,row in df.iterrows(): 
            cols = st.beta_columns([1,1,1,5])
            cols[0].text(i)
            cols[1].text(row["count"])
            cols[2].text(df1.loc[i])
            cols[3].text(row["cases"].replace("<br>",""))




#UI start date end date filtering assume dataframe already in date format
def date_options(df,col):
    min_date = df[col].min()-timedelta(days=7)
    max_date = datetime.today().date()#df[col].max()+timedelta(days=31) #lets just go a month out actually lets do today
    cols = st.beta_columns(2)
    start_date = cols[0].date_input("Start Date",min_value=min_date,max_value=max_date,value=min_date)#,format="MM/DD/YY")
    end_date = cols[1].date_input("End Date",min_value=min_date,max_value=max_date,value=max_date)#,format="MM/DD/YY")
    df = filter_dates(df,start_date,end_date,col)
    return df


def filter_dates(df,start_date,end_date,col):
    return df.loc[(df[col].apply(lambda x: x)>=start_date) & (df[col].apply(lambda x: x)<=end_date)]


#change try excepts to check empty and return if none for df_r and cs agg cases
def overview(el,cl,cc,df_cc,df_fu,pir):
#    with st.beta_expander("Data Overview for all Tenants"):
    #Date filter
    #Call Status break downs not unique cases...
    cl_f = date_options(cl,"Date Contact Made or Attempted")
    df_cc = cl_f.loc[cl_f["Status of Call"].eq("Spoke with tenant call completed")].drop_duplicates("Case Number") 
   
    cols = st.beta_columns([1,1,1,1]) 
    cols[0].markdown(f"### :phone: Calls made: {len(cl_f)} ")
    cols[1].markdown(f"### :mantelpiece_clock: Time on calls: {cl_f.groupby('Caller Name')['Length Call (minutes)'].sum().sum()} minutes")
    cols[2].markdown(f"### :ballot_box_with_check: Completed Calls: {len(df_cc['Case Number'].unique())}") #Do we want to only have unique case numbers?
    cols[3].markdown(f"### :muscle: Cases Called: {len(cl_f['Case Number'].unique())}") 

   
    #Completed Calls 
    #Call Status piechart
    #Completed call break downs: 
    display = ['Still living at address?','Knows about moratorium?','Knows about the eviction?','Eviction for Non-Payment?','LL mentioned eviction?','Rental Assistance Applied?','Repairs issues?']	
    dfs= []
    columns = df_cc.columns
     
    for i,col in enumerate(columns):
        if col in display:
            try: #if agg columns had no data
                df_r = agg_cases(df_cc,col,i)
            except:
                df_r = None
            if df_r is not None:
              df_r.columns = ["Count","Cases"]
              df_r = df_r.reset_index(level=[0]) # 
              dfs.append(df_r)

    st.text("")
    st.text("")
    cols = st.beta_columns(len(display))
    for i, df in enumerate(dfs):
        cols[i].markdown(f"#### {display[i]}")
        cols[i].text("")

    for i, df in enumerate(dfs): #Sort change to ["Yes","No","Unknown"]
        for vals in df.values:
            cols[i].markdown(f"{vals[0]}: {vals[1]}/{df['Count'].sum()}")
    try:
        cs = agg_cases(cl_f,"Status of Call",0,True) 
    except:
        cs = None
    if cs is not None:
        fig = px.pie(cs, values="count", names=cs.index, title="Call Status Break Down",hover_data=["cases"])
        fig.update_traces(textinfo='value')
        cols = st.beta_columns([2,1])
        cols[0].plotly_chart(fig)

        #Call Status numbers
        cols[1].text("")
        cols[1].text("")
        cols[1].markdown("#### Break downs for call status:")
        cols[1].write(cs["count"])
        cols[1].text("")
        cols[1].text("")

        #Case number contact bar graph
        st.markdown("#### Call Counts")
        #cn = date_options(cn,"Date Contact Made or Attempted")
        fig = px.bar(cl_f,x="Case Number",y="count",color="Caller Name",hover_data=["count","Date Contact Made or Attempted","Status of Call","Status"])
# fi    g.update_layout(yaxis={'visible': False, 'showticklabels': False})
        st.plotly_chart(fig,use_container_width=True)
        
        #Completed call information
        st.markdown("#### Completed Calls for the date range all information")
        st.write(df_cc)


def side_bar(cl,df_cc,el,cc,df_fu):
    """Compute and render data for the sidebar (Excludes Sidebar UI)"""
    st.sidebar.markdown(f"### Total calls made: {len(cl)} ")
    st.sidebar.markdown(f"### Total time on calls: {cl.groupby('Caller Name')['Length Call (minutes)'].sum().sum()} minutes")
    st.sidebar.markdown(f"### Completed Calls: {len(df_cc['Case Number'].unique())}") #Do we want to only have unique case numbers?
    st.sidebar.markdown(f"### Emails Sent: {len(el['Case Number'].unique())-len(el.loc[el['Email Method'].eq('')])}") #Errors are logged as "" in Email log gsheet
    st.sidebar.markdown(f"### Cases Called: {len(cl['Case Number'].unique())}") 
    st.sidebar.markdown(f"### Cases Not Yet Called: {len(cc.loc[~cc['unique search'].eq('')])}") 
    st.sidebar.markdown(f"### Calls to Follow Up: {len(df_fu['Case Number'].unique())}")


def time_series_graph(pir,cl,ev):
    #call counts vs. not called counts  vs filing counts vs contact counts (with phone numbers) all unique 
    #for contact counts aggregate by week take max date -6 days and sum unique cases with that filter (add 7 to max date to get day contacts came in)
    #filter completed vs non completed calls
    df_cc = cl.loc[cl["Status of Call"].eq("Spoke with tenant call completed")].drop_duplicates("Case Number")  
    df_nc = cl.loc[~cl["Status of Call"].eq("Spoke with tenant call completed")].drop_duplicates("Case Number")
    
    #aggregate by week 
    num_days = 7
    #add and calculate column upload date to contact data
    min_date = pd.to_datetime(cl["Date Contact Made or Attempted"]).min().date()
    max_date = pd.to_datetime(cl["Date Contact Made or Attempted"]).max().date() #when we started making calls to now
    pir = aggregate_by_days(pir,"File Date","agg_date",min_date,max_date,num_days)
    pir["upload_date"] = pir["agg_date"] + timedelta(days=7)
    #add and calculate column agg_date to call list for cases called and tenants spoken to
    cl = aggregate_by_days(cl,"Date Contact Made or Attempted","agg_date",min_date,max_date,num_days)
    df_cl = cl.groupby("agg_date").agg("count")[["Case Number","Defendant"]]#count is cases called and "nunique is unique case"
    df_cl["Cases Called"] = df_cl["Case Number"] 
    cl_cc = cl.loc[cl["Status of Call"].eq("Spoke with tenant call completed")]
    df_cc = cl_cc.groupby("agg_date").agg("nunique")[["Case Number","Defendant"]]
    df_cc["Tenants Spoken With"] = df_cc["Case Number"]
    #add and calculate column agg_date for unique eviction cases filed
    ev =  filter_dates(ev,min_date,max_date,"date_filed")
    ev =  aggregate_by_days(ev,"date_filed","agg_date",min_date,max_date,num_days)  
    df_ev = ev.groupby("agg_date").agg("nunique")[["case_number","defendants"]]
    df_ev["Cases Filed"] = df_ev["case_number"]
    #calculate aggregates to graph
    df_pir = pir.groupby("upload_date").agg("nunique")[["Cell Phone","Home Phone"]]
    df = df_cl.merge(df_pir,left_index=True,right_index=True,how='outer')
    df = df.merge(df_cc,left_index=True,right_index=True,how='outer')
    df = df.merge(df_ev,left_index=True,right_index=True,how='outer')
    df.fillna(0,inplace=True)
    df["New Contacts"] = df["Cell Phone"] + df["Home Phone"]
    st.markdown("### Volunteer Activity  vs. Court Activity")
    st.plotly_chart(
        df[["New Contacts","Cases Called","Tenants Spoken With","Cases Filed"]].iplot(
            kind='lines', 
            size = 5,
            rangeslider=True, 
            asFigure=True
        ),
        use_container_width = True,
        height = 200
    )
 
def aggregate_by_days(pir,col,out_col,min_date,max_date,num_days): 
    #assuming we get contacts in once a week on the same day (7 days apart) and they come in a week after the filing date
    #round everything to the nearest week 
#    min_date = pd.to_datetime(pir["File Date"]).min().date() #change to when we first started getting information
    #precompute upload dates
    min_date = min_date - timedelta(days=num_days*2) #make sure we are including min date range
    upload_dates = [max_date - timedelta(days=x*num_days) for x in range(int((max_date-min_date).days/num_days))]
    #create ranges 
    date_ranges = list(zip(upload_dates[0::1],upload_dates[1::1])) 
    #go through ranges and assign upload dates 
    for date_range in date_ranges:
        pir.at[
            pir.loc[
                (pir[col]<=(date_range[0])) & 
                (pir[col]>(date_range[1])) 
            ].index,
            out_col
        ] = date_range[0] 
    return pir


#maybe sort in render page and then drop duplicates so follow ups get droped?
def render_page(el,cl,cc,ev,pir):
    """Compute sub data frames for page rendering and call sub render functions"""
    #Make sub data frames
    #Follow up calls to make: not unique for case number Looks at cases still in follow up list (Follow up list is generated and maintained in community lawyer) A call is taken out if a case is dismissed (from PIR integration) or a volunteer marks completed call or do not call back
    df_fu = cl.loc[cl["Case Number"].isin(cc.loc[~cc['unique search follow up'].eq("")]["Case Number"])]
    #Calls to make: not unique for case number
    df_c2m = cc.loc[~cc['unique search'].eq("")]
    #Completed Calls: for overview (only completed calls info) unique for case number 
    df_cc = cl.loc[cl["Status of Call"].eq("Spoke with tenant call completed")].drop_duplicates("Case Number") 
    df_cc.replace("","Unknown",inplace=True)#replace "" entries with unknonw
    #Completed Calls: for list (includes follow up calls) not unique for case number
    df_cc_fu = cl.loc[cl["Case Number"].isin(df_cc["Case Number"])]
    #Not yet contacted cases
    df_nc = cc.loc[~cc['unique search'].eq("")] #Have calls that were not made yet or were never made in All data set
    #All cases: includes email logs call logs and calls not yet made information
    df_ac = pd.concat([df_nc,cl,el])
    #Contact Failed not in contact list (cc) follow up not in call completed list (df_cc) 
    df_cf = cl.loc[~cl["Case Number"].isin(df_cc["Case Number"]) & ~cl["Case Number"].isin(df_fu["Case Number"])]
    #clean volunteer names
    cl["Caller Name"] = cl["Caller Name"].str.rstrip(" ") 
    #Render sub-pages
#    tenant_details(el,cl,cc,df_cc_fu,df_fu,df_ac,df_nc,df_cf) 
    side_bar(cl,df_cc,el,cc,df_fu)
    overview(el,cl,cc,df_cc,df_fu,pir)
    time_series_graph(pir,cl,ev) 
    volunteer_details(cl)    


if __name__ == "__main__":
    #Read in data
    if LOCAL:
        st.set_page_config(layout="wide")
        el = pd.read_csv('../data/RRT_contacts_cl - Email_log.csv')
        cl = pd.read_csv('../data/RRT_contacts_cl - Call_log.csv')
        cc = pd.read_csv('../data/RRT_contacts_cl - Contact_list.csv')
        ev = pd.read_csv('../data/Court_scraper_evictions_archive - evictions_archive.csv')
        es = pd.read_csv('../data/Court_scraper_eviction_scheduler - eviction_scheduler.csv')
        pir = pd.read_csv('../data/Court_contact_data_PIR.csv')
        #Convert to date
        el = convert_date(el,"Date Emailed")
        cl = convert_date(cl,"Date Contact Made or Attempted")
        ev = convert_date(ev,"date_filed")
        pir = convert_date(pir,"File Date")
        #Sort log entries by time (most recent first)
        el.sort_values(by=["Date Emailed"],inplace=True,ascending=False)
        cl.sort_values(by=["Date Contact Made or Attempted"],inplace=True,ascending=False)
        ev.sort_values(by=["date"],inplace=True,ascending=False)
        pir.sort_values(by=["File Date"],inplace=True,ascending=False)
        #Clean up for use 
    #    cl["Length Call (minutes)"] = cl["Length Call (minutes)"].replace("",0).astype(int)
        cl["count"] = 1 #for call count bar chart (probably better way to do this
        render_page(el,cl,cc,ev,pir)
    else:
        creds = st_config()
        #Credentials check
        if creds is not None: 
            el = copy.deepcopy(read_data(creds,"RRT_contacts_cl","Email_log")) #Displays invalid API Key error on web page
            cl = copy.deepcopy(read_data(creds,"RRT_contacts_cl","Call_log"))
            cc = copy.deepcopy(read_data(creds,"RRT_contacts_cl","Contact_list"))
            ev = copy.deepcopy(read_data(creds,"Court_scraper_evictions_archive","evictions_archive"))
            pir = copy.deepcopy(read_data(creds,"Court_contact_data_PIR",0))
            
            #Convert to date
            el = convert_date(el,"Date Emailed")
            cl = convert_date(cl,"Date Contact Made or Attempted")
            ev = convert_date(ev,"date_filed")
            pir = convert_date(pir,"File Date")
            #Sort log entries by time (most recent first)
            el.sort_values(by=["Date Emailed"],inplace=True,ascending=False)
            cl.sort_values(by=["Date Contact Made or Attempted"],inplace=True,ascending=False)
            ev.sort_values(by=["date"],inplace=True,ascending=False)
            pir.sort_values(by=["File Date"],inplace=True,ascending=False)
            #Clean up for use 
            cl["Length Call (minutes)"] = cl["Length Call (minutes)"].replace("",0).astype(int)
            cl["count"] = 1 #for call count bar chart (probably better way to do this
            render_page(el,cl,cc,ev,pir)
        else: 
            caching.clear_cache()
            st.text(f"Invalid password.")
    
    #Case number contact bar graph
#    cn = cl.sort_values("Date Contact Made or Attempted")

    #Resources requested and shared break downs
#    rr = agg_cases(cl,"Best way to send resources",0,True)   
#    rr = agg_checklist(rr)
#    rr = rr.drop("")
#    rr.columns = ["count","cases"]
#    rr1 = agg_cases(cl,"Sent Resources via Text?",0,True)
#    rr1 = agg_checklist(rr1)
#    rr1.index = rr1.index.str.strip(" ")
#    rr1.columns = ["count","cases"]
#    rr1 = rr1.drop("")
#    rr1 = rr1.drop(",")
#    
#    rr2 = agg_cases(cl,"Resources Requested",0,True)
#    rr2 = agg_checklist(rr2)
#    rr2.index = rr2.index.str.strip(" ")
#    rr2.columns = ["count","cases"]
#    rr2 = rr2.drop("")
#    rr2_t1 = rr2.groupby(level=0).sum()
#    rr2_t2 = rr2.groupby(level=0).agg(lambda x: ",".join(x))
#    rr2 = rr2_t1.merge(rr2_t2,right_index=True,left_index=True)   
#    
#    rr3 = agg_cases(cl,"Sent Resources via Email?",0,True)
#    rr3 = rr3.drop("")
#    rr3.index = ["Emailed Resources"]
#    
#    rr1 = pd.concat([rr3,rr1]) #Bring in email data to data about resources sent
#    rr1["sent_req"]="sent"
#    rr2["sent_req"]="requested" #requested 
 
    #Follow up reason
    #fu = agg_cases(df_fu,"Follow Up Reason",0,True)
    #fu = agg_checklist(fu)
    #fu = fu.drop("")
    #fu.columns = ["count","cases"]
 
    
