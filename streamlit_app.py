import copy
import datetime
from datetime import datetime
import altair as alt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import gsheet
from streamlit import caching
#See gsheet for fetching local creds
def st_config():
    """Configure Streamlit view option and read in credential file if needed"""
    st.set_page_config(layout="wide")
    creds = st.sidebar.text_area("Enter API Key:")
    return creds


@st.cache
def read_data(creds,ws,gs):
    """Read court tracking data in and drop duplicate case numbers"""
    try:
        df = gsheet.read_data(gsheet.open_sheet(gsheet.init_sheets(creds),ws,gs))
    #    df.drop_duplicates("Case Number",inplace=True) #Do we want to drop duplicates???
        return df
    except Exception as e:
        return None


def convert_date(df,col):
    """Helper function to convert a col to a date"""
    df[col] = pd.to_datetime(df[col]).apply(lambda x: x.date())
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


def render_tenants(df,option):
    """Helper function to render individual logs"""
    df = df.groupby("Case Number") #consolidate cases for display
    for i,group in df:
        with st.beta_expander(str(option + ": " + i + " " + group["Defendant"].str.title().values[0])): #has case number and defendant name(s)
            #Display info  
            count = 0
            for name,row in group.iterrows(): 
                for j in row.index:
                    if j == "Case Number": #probably better way to seperate calls...and compute call count
                        count += 1
                        st.markdown(f"### Log Entry")
                    if str(row[j]) != "nan":  #!!!!!!BUG WHY IS nan not working here? HAVE TO DO TWO LAYERS OF IF WHY???
                       if row[j] != "":
                           cols = st.beta_columns([2,6])
                           cols[0].text(j)
                           cols[1].text(row[j])
            st.markdown(f"### Call Count: {count}") 


#df_cc is df_cc_fu (has follow ups in int too)
def tenant_details(el,cl,cc,df_cc,df_fu,df_ac,df_nc,df_cf):
    """Compute filter and render logs"""
    #Render UI filter
    st.sidebar.markdown("### Log Display Options")
    cc = st.sidebar.checkbox("Completed Calls")
    fu = st.sidebar.checkbox("Follow Up Calls")
    em = st.sidebar.checkbox("Emails")
    ac = st.sidebar.checkbox("All Cases (contacted and not yet contacted)")
    
    #Build search list for drop down select box has case number and case style in drop down has unique case numbers (but renders multiple)
    l = []
    if cc:
        for x,y in zip(df_cc["Case Number"].drop_duplicates().values.tolist(),df_cc.drop_duplicates("Case Number")["Defendant"].str.upper().values.tolist()): 
            l.append(str(x)+" "+str(y))
    if fu:
        for x,y in zip(df_fu["Case Number"].drop_duplicates().values.tolist(),df_fu.drop_duplicates("Case Number")["Defendant"].str.upper().values.tolist()): 
            l.append(str(x)+" "+str(y))
    if em:
        for x,y in zip(el["Case Number"].drop_duplicates().values.tolist(),el.drop_duplicates("Case Number")["Defendant"].str.upper().values.tolist()):
            l.append(str(x)+" "+str(y))
    if ac:
        l = [] # if we are doing all the cases we don't need to worry about the other entries they are already there...
        for x,y in zip(df_ac["Case Number"].drop_duplicates().values.tolist(),df_ac.drop_duplicates("Case Number")["Defendant"].str.upper().values.tolist()):
            l.append(str(x)+" "+str(y))
    l.insert(0,"All")
    case = st.selectbox("Search Cases",l) 
    
    #Build list based on filter
    if case == "All":
        if ac:
            render_tenants(df_cc,"Completed Call")   
            render_tenants(df_fu,"Follow Up")   
            render_tenants(el,"Emailed")        
            render_tenants(df_nc,"Not Yet Contacted")        
            render_tenants(df_cf,"Contact Failed") 
        else: # dont need to rerender the others if its alreday been done...
            if cc: #display completed first maybe do a pd.concat and dfs.append instead of render individually?
                render_tenants(df_cc,"Completed Call")   
            if fu:
                render_tenants(df_fu,"Follow Up")   
            if em:
                render_tenants(el,"Emailed")        
            if not(cc or fu or em):
                st.text("Please select a Display Option in the sidebar to view logs.")
    else: #single case
        if ac: #Detemine call type
            if df_cc["Case Number"].str.contains(case.split(" ")[0],na=False).any(): call_type = "Completed Call"
            elif df_fu["Case Number"].str.contains(case.split(" ")[0],na=False).any(): call_type = "Follow Up"
            elif el["Case Number"].str.contains(case.split(" ")[0],na=False).any(): call_type = "Emailed"
            elif df_nc["Case Number"].str.contains(case.split(" ")[0],na=False).any(): call_type = "Not Yet Contacted"
            else: call_type = "Contact Failed"
            render_tenants(df_ac.loc[df_ac["Case Number"].str.contains(case.split(" ")[0],na=False)],call_type) #search df for case number (search box returns case number tenant name etc. seperated by a space   
        if cc: 
            render_tenants(df_cc.loc[df_cc["Case Number"].str.contains(case.split(" ")[0],na=False)],"Completed Call") #search df for case number (search box returns case number tenant name etc. seperated by a space   
        if fu:
            render_tenants(df_fu.loc[df_fu["Case Number"].str.contains(case.split(" ")[0],na=False)],"Follow Up")   
        if em:
            render_tenants(el.loc[el["Case Number"].str.contains(case.split(" ")[0],na=False)],"Emailed")        
    return 


#UI start date end date filtering assume dataframe already in date format
def date_options(df,col):
    min_date = df[col].min()
    max_date = df[col].max()
    cols = st.beta_columns(2)
    start_date = cols[0].date_input("Start Date",min_value=min_date,max_value=max_date,value=min_date)#,format="MM/DD/YY")
    end_date = cols[1].date_input("End Date",min_value=min_date,max_value=max_date,value=max_date)#,format="MM/DD/YY")
    df = filter_dates(df,start_date,end_date,col)
    return df


def filter_dates(df,start_date,end_date,col):
    return df.loc[(df[col].apply(lambda x: x)>=start_date) & (df[col].apply(lambda x: x)<=end_date)]


def overview(el,cl,cc,df_cc,df_fu):
    #Completed call break downs: 
    display = ['Still living at address?','Knows about moratorium?','Knows about the eviction?','Eviction for Non-Payment?','LL mentioned eviction?','Rental Assistance Applied?','Repairs issues?']	
    dfs= []
    columns = df_cc.columns
    for i,col in enumerate(columns):
        if col in display:
            df_r = agg_cases(df_cc,col,i)
            df_r.columns = ["Count","Cases"]
            df_r = df_r.reset_index(level=[0]) # 
#            try: #Fails where no na's I think this can be kept out
#                count_na = str(df_r.loc[""]["Count"])
#                df_r = df_r.drop("")
#            except:
#                count_na = 0

            if not df_r.empty:
                dfs.append(df_r)

    #Call Status break downs not unique cases...
    cs = agg_cases(cl,"Status of Call",0,True) 
   
    #Case number contact bar graph
    cn = cl.sort_values("Date Contact Made or Attempted")

    #Resources requested and shared break downs
    rr = agg_cases(cl,"Best way to send resources",0,True)   
    rr = agg_checklist(rr)
    rr = rr.drop("")
    rr.columns = ["count","cases"]
    rr1 = agg_cases(cl,"Sent Resources via Text?",0,True)
    rr1 = agg_checklist(rr1)
    rr1.index = rr1.index.str.strip(" ")
    rr1.columns = ["count","cases"]
    rr1 = rr1.drop("")
    rr1 = rr1.drop(",")
    
    rr2 = agg_cases(cl,"Resources Requested",0,True)
    rr2 = agg_checklist(rr2)
    rr2.index = rr2.index.str.strip(" ")
    rr2.columns = ["count","cases"]
    rr2 = rr2.drop("")
    rr2_t1 = rr2.groupby(level=0).sum()
    rr2_t2 = rr2.groupby(level=0).agg(lambda x: ",".join(x))
    rr2 = rr2_t1.merge(rr2_t2,right_index=True,left_index=True)   
    
    rr3 = agg_cases(cl,"Sent Resources via Email?",0,True)
    rr3 = rr3.drop("")
    rr3.index = ["Emailed Resources"]
    
    rr1 = pd.concat([rr3,rr1]) #Bring in email data to data about resources sent
    rr1["sent_req"]="sent"
    rr2["sent_req"]="requested" #requested 
 
    #Follow up reason
    #fu = agg_cases(df_fu,"Follow Up Reason",0,True)
    #fu = agg_checklist(fu)
    #fu = fu.drop("")
    #fu.columns = ["count","cases"]
 
    with st.beta_expander("Data Overview for all Tenants"):
        cols = st.beta_columns(2)
        #Call Status
        fig = px.pie(cs, values="count", names=cs.index, title="Call Status Break Down",hover_data=["cases"])
        fig.update_traces(textinfo='value')
        cols[0].plotly_chart(fig)

        #Average call count for completion
        fig = px.pie(rr, values="count", names=rr.index, title="Preferred Contact Method",hover_data=["cases"])
        fig.update_traces(textinfo='value')
        cols[1].plotly_chart(fig)               
    
        #Case number contact bar graph
        st.markdown("#### Call Counts")
        cn = date_options(cn,"Date Contact Made or Attempted")
        fig = px.bar(cn,x="Case Number",y="count",color="Caller Name",hover_data=["count","Date Contact Made or Attempted","Status of Call","Status"])
#    fig.update_layout(yaxis={'visible': False, 'showticklabels': False})
        st.plotly_chart(fig,use_container_width=True)
        
        #Resources Requested and Shared Add column back to CL for it to work
        st.markdown("### Resources Requested and Shared") 
        rr2=pd.concat([rr1,rr2])
        fig = px.bar(rr2, x=rr2.index, y="count",color="sent_req",hover_data=["cases"]) #maybe sort special???
        st.plotly_chart(fig,use_container_width=True)
        
        #Completed Calls 
        cols = st.beta_columns(len(display))
        for i, df in enumerate(dfs):
            cols[i].markdown(f"#### {display[i]}")
        for i, df in enumerate(dfs): #Sort change to ["Yes","No","Unknown"]
            bg = alt.Chart(df).mark_bar().encode(x=alt.X(display[i], axis=alt.Axis(title=None,labelAngle=0), sort=["Yes","No","Unknown"]),y='Count',tooltip=[display[i],"Count","Cases"],color=alt.Color(display[i], legend=None)).properties(height=150)
            cols[i].altair_chart(bg, use_container_width=True)
    return 

def side_bar(cl,df_cc,el,cc,df_fu):
    """Compute and render data for the sidebar (Excludes Sidebar UI)"""
    st.sidebar.markdown(f"### Total calls made: {len(cl)} ")
    st.sidebar.markdown(f"### Total time on calls: {cl.groupby('Caller Name')['Length Call (minutes)'].sum().sum()} minutes")
    st.sidebar.markdown(f"### Completed Calls: {len(df_cc['Case Number'].unique())}") #Do we want to only have unique case numbers?
    st.sidebar.markdown(f"### Emails Sent: {len(el['Case Number'].unique())-len(el.loc[el['Email Method'].eq('')])}") #Errors are logged as "" in Email log gsheet
    st.sidebar.markdown(f"### Cases Called: {len(cl['Case Number'].unique())}") 
    st.sidebar.markdown(f"### Cases Not Yet Called: {len(cc.loc[~cc['unique search'].eq('')])}") 
    st.sidebar.markdown(f"### Calls to Follow Up: {len(df_fu['Case Number'].unique())}")


#maybe sort in render page and then drop duplicates so follow ups get droped?
def render_page(el,cl,cc):
    """Compute sub data frames for page rendering and call sub render functions"""
    #Make sub data frames
    #Follow up calls to make: not unique for case number Looks at cases still in follow up list (Follow up list is generated and maintained in community lawyer) A call is taken out if a case is dismissed (from PIR integration) or a volunteer marks completed call or do not call back
    df_fu = cl.loc[cl["Case Number"].isin(cc.loc[~cc['unique search follow up'].eq("")]["Case Number"])]
    #Calls to make: not unique for case number
    df_c2m = cc.loc[~cc['unique search'].eq("")]
    #Completed Calls: for overview (only completed calls info) unique for case number 
    df_cc = cl.loc[cl["Status of Call"].eq("Spoke with tenant call completed")].drop_duplicates("Case Number") 
    #Completed Calls: for list (includes follow up calls) not unique for case number
    df_cc_fu = cl.loc[cl["Case Number"].isin(df_cc["Case Number"])]
    #Not yet contacted cases
    df_nc = cc.loc[~cc['unique search'].eq("")] #Have calls that were not made yet or were never made in All data set
    #All cases: includes email logs call logs and calls not yet made information
    df_ac = pd.concat([df_nc,cl,el])
    #Contact Failed not in contact list (cc) follow up not in call completed list (df_cc) 
    df_cf = cl.loc[~cl["Case Number"].isin(df_cc["Case Number"]) & ~cl["Case Number"].isin(df_fu["Case Number"])]
    
    #Render sub-pages
    tenant_details(el,cl,cc,df_cc_fu,df_fu,df_ac,df_nc,df_cf) 
    side_bar(cl,df_cc,el,cc,df_fu)
    overview(el,cl,cc,df_cc,df_fu)
    volunteer_details(cl)    


if __name__ == "__main__":
    #Read in data
    creds = st_config()
    el = copy.deepcopy(read_data(creds,"RRT_contacts_cl","Email_log")) #Displays invalid API Key error on web page
    cl = copy.deepcopy(read_data(creds,"RRT_contacts_cl","Call_log"))
    cc = copy.deepcopy(read_data(creds,"RRT_contacts_cl","Contact_list"))
    #Credentials check
    if el is not None: 
        #Convert to date
        el = convert_date(el,"Date Emailed")
        cl = convert_date(cl,"Date Contact Made or Attempted")
        #Sort log entries by time (most recent first)
        el.sort_values(by=["Date Emailed"],inplace=True,ascending=False)
        cl.sort_values(by=["Date Contact Made or Attempted"],inplace=True,ascending=False)
        #Clean up for use 
        cl["Length Call (minutes)"] = cl["Length Call (minutes)"].replace("",0).astype(int)
        cl["count"] = 1 #for call count bar chart (probably better way to do this
        render_page(el,cl,cc)
    else: 
        caching.clear_cache()
        st.text(f"Invalid API key")
    
    
