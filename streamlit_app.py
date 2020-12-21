import copy
import datetime
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import gsheet

#should I have local dev read in .env?
def st_config():
    """Configure Streamlit view option and read in credential file if needed"""
    st.set_page_config(layout="wide")
    creds = st.sidebar.text_area("Enter API Key:")
    return creds

#Also test creds?
@st.cache
def read_data(creds,ws,gs):
#    """Read court tracking data in and drop duplicate case numbers"""
    try:
        df = gsheet.read_data(gsheet.open_sheet(gsheet.init_sheets(creds),ws,gs))
    #    df.drop_duplicates("Case Number",inplace=True) #Do we want to drop duplicates???
        return df
    except Exception as e:
        return None

def agg_checklist(df_r):
    df_r["result"]=df_r.index
    df_b = pd.concat([pd.Series(row['count'], row['result'].split(', ')) for _,row in df_r.iterrows()]).reset_index().groupby("index").sum()
    df_a = pd.concat([pd.Series(row['cases'], row['result'].split(', ')) for _,row in df_r.iterrows()]).reset_index().groupby("index").agg(lambda x: ", ".join(x))
    df_r = df_b.merge(df_a,right_index=True,left_index=True)
    return df_r


def agg_cases(df,col,i):
    df_r = df.groupby([col,"Case Number"]).count().iloc[:,i]
    df_r.name = "count"
    df_r = pd.DataFrame(df_r)
    df_a = pd.DataFrame(df_r.to_records())
    df_r = df_r.groupby(level=0).sum()
    df_r["cases"] = df_a.groupby(col)["Case Number"].agg(lambda x: ','.join(x))
    return df_r

#Include bar graph Date Contact Made or Attempted
def volunteer_details(cl):
    df = agg_cases(cl,"Caller Name",0)
    #total minutes on phone per caller
    cl["Length Call (minutes)"] = cl["Length Call (minutes)"].replace("",0).astype(int)
    df1 = cl.groupby("Caller Name")["Length Call (minutes)"].sum()
    #Calls over time 
    df2 = agg_cases(cl,"Date Contact Made or Attempted",0)
      
    st.sidebar.markdown(f"### Total calls made: {len(cl)} ")
    st.sidebar.markdown(f"### Total time on calls: {df1.sum()} minutes")
    
    #calls made per tracker
    with st.beta_expander("Volunteer Information"):
        cols = st.beta_columns([1,1])
        cols[0].plotly_chart(px.pie(df, values='count', names=df.index, title='Volunteer Call Count'))
        cols[1].plotly_chart(px.pie(df1, values='Length Call (minutes)', names=df1.index, title='Volunteer Call Time'))
       
        st.text("Calls over time") 
        st.line_chart(df2["count"],height=200)        
 
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
            cols[3].text(row["cases"])


def render_tenants(df,option):
    df = df.groupby("Case Number") #consolidate cases for display
    for i,group in df:
        with st.beta_expander(str(option + ": " + i + " " + group["Case Style"].str.title().str.split("Vs. ").values[0][1])): #has case number and defendant name(s)
            #Display info  
            count = 0
            for name,row in group.iterrows(): 
                for j in row.index:
                    if j == "Case Number": #probably better way to seperate calls...and compute call count
                        count += 1
                        st.markdown(f"### Log Entry")
                    if (row[j] != ""): #figure out what to do about sent resources? df["Sent Resources via Text?"].strip
                       cols = st.beta_columns([1,5])
                       cols[0].text(j)
                       cols[1].text(row[j])
            st.markdown(f"### Call Count: {count}") 

def tenant_details(el,cl):
    #sort log entries by time (most recent first) maybe get rid of columns and just  call them date so tehy are consistant?
    el["Date Emailed"] = pd.to_datetime(el["Date Emailed"]).apply(lambda x: x.date())
    cl["Date Contact Made or Attempted"] = pd.to_datetime(cl["Date Contact Made or Attempted"]).apply(lambda x: x.date())
    el.sort_values(by=["Date Emailed"],inplace=True,ascending=False)
    cl.sort_values(by=["Date Contact Made or Attempted"],inplace=True,ascending=False)
    
    ####WHAT TO DO ABOUT CALLS WITH NO FOLLOW UP SET BUT WERE NOT COMPLETED??? Currently keeping them in follow up list?
    st.sidebar.markdown("### Log Display Options")
    cc = st.sidebar.checkbox("Completed Calls")
    fu = st.sidebar.checkbox("Follow Up Calls")
    em = st.sidebar.checkbox("Emails")
    #cols = st.beta_columns([1,1,1])
    #cc = cols[0].checkbox("Completed Calls")
    #fu = cols[1].checkbox("Follow Up Calls")
    #em = cols[2].checkbox("Emails")

    df_cc = cl.loc[cl["Status of Call"].eq("Spoke with tenant call completed")]#.drop_duplicates("Case Number") #dropping duplicates we should not have any duplicates?
    df_cc = cl.loc[cl["Case Number"].isin(df_cc["Case Number"])]  #for completed calls we want all logs displayed even the ones with follow ups!
    df_fu = cl.drop(df_cc.index) #keeping calls that are not in the Follow Up ie Hung Up or Disconnected? 
    #build search list for drop down select box has case number and case style in drop down
    l = []
    if cc:
        for x,y in zip(df_cc["Case Number"].drop_duplicates().values.tolist(),df_cc.drop_duplicates("Case Number")["Case Style"].str.upper().values.tolist()): 
            l.append(x+" "+y)
    if fu:
        for x,y in zip(df_fu["Case Number"].drop_duplicates().values.tolist(),df_fu.drop_duplicates("Case Number")["Case Style"].str.upper().values.tolist()): #only display case numbers once
            l.append(x+" "+y)
    if em:
        for x,y in zip(el["Case Number"].drop_duplicates().values.tolist(),el.drop_duplicates("Case Number")["Case Style"].str.upper().values.tolist()):
            l.append(x+" "+y)
    l.insert(0,"All")
    case = st.selectbox("Search Cases",l) #ALSO INCLUDE TENANT NAME AND OTHER DETAILS?
    
    if case == "All":
    #show all logs for selected cc and/or fu and/or em in collapsable menus (annotate email or call) This will be indented if drop down menu uncommented
        if cc: #display completed first maybe do a pd.concat and dfs.append instead of render individually?
            render_tenants(df_cc,"Completed Call")   
        if fu:
            render_tenants(df_fu,"Follow Up")   
        if em:
            render_tenants(el,"Emailed")        
        if not(cc or fu or em):
            st.text("Please select a Display Option in the sidebar to view logs.")
    else: #single case
        if cc: #display completed first maybe do a pd.concat and dfs.append instead of render individually?
            render_tenants(df_cc.loc[df_cc["Case Number"].str.contains(case.split(" ")[0],na=False)],"Completed Call") #search df for case number (search box returns case number tenant name etc. seperated by a space   
        if fu:
            render_tenants(df_fu.loc[df_fu["Case Number"].str.contains(case.split(" ")[0],na=False)],"Follow Up")   
        if em:
            render_tenants(el.loc[el["Case Number"].str.contains(case.split(" ")[0],na=False)],"Emailed")        
    return 

def overview(el,cl):
    #Tenant info bargraph break downs
    df_cc = cl.loc[cl["Status of Call"].eq("Spoke with tenant call completed")].drop_duplicates("Case Number") #do we want to drop duplicates? 
    df_fu = cl.drop(df_cc.index) #keeping calls that are not in the Follow Up ie Hung Up or Disconnected? 
    
    #Completed call break downs: 
    display = ['Still living at address?','Knows about moratorium?','Knows about the eviction?','Eviction for Non-Payment?','LL mentioned eviction?','Rental Assistance Applied?']	
    dfs= []
    columns = df_cc.columns
    for i,col in enumerate(columns):
        if col in display:
            df_r = agg_cases(df_cc,col,i)
            df_r.columns = ["Count","Cases"]
            
            try: #Fails where no na's
                count_na = str(df_r.loc[""]["Count"])
                df_r = df_r.drop("")
            except:
                count_na = 0

            if not df_r.empty:
                dfs.append(df_r)

    #Call Status break downs not unique cases...
    cs = agg_cases(cl,"Status of Call",0) 
   
    #Resources requested and shared break downs
    rr = agg_cases(cl,"Best way to send resources",0)   
    rr = agg_checklist(rr)
    rr = rr.drop("")
    rr.columns = ["count","cases"]
    rr1 = agg_cases(cl,"Sent Resources via Text?",0)
    rr1 = agg_checklist(rr1)
    rr1.index = rr1.index.str.strip(" ")
    rr1 = rr1.groupby(level=0).sum()
    rr1 = rr1.drop("")
    rr1 = rr1.drop(",")
    rr1.columns = ["count"]
    rr2 = agg_cases(cl,"Resources Requested",0)
    rr2 = agg_checklist(rr2)
    rr2.index = rr2.index.str.strip(" ")
    rr2 = rr2.groupby(level=0).sum()
    rr2 = rr2.drop("")
    rr2.columns = ["count"]
    rr3 = agg_cases(cl,"Sent Resources via Email?",0)
    rr3 = rr3.drop("")
    rr3 = rr3.drop("cases",axis=1) 
    rr3.index = ["Emailed Resources"]
    rr1 = pd.concat([rr3,rr1]) # Bring in email data to data about resources sent
 
# Resources Requested	Sent Resources via Text?	Best way to send resources
    st.sidebar.markdown(f"### Completed Calls: {len(df_cc['Case Number'].unique())}") #Do we want to only have unique case numbers?
    st.sidebar.markdown(f"### Emails Sent: {len(el['Case Number'].unique())}") 
    st.sidebar.markdown(f"### Cases Called: {len(cl['Case Number'].unique())}") 
    st.sidebar.markdown(f"### Calls to Follow Up: {len(df_fu['Case Number'].unique())}")
    with st.beta_expander("Data Overview for all Tenants"):
        cols = st.beta_columns(2)
        #Call Status
        cols[0].plotly_chart(px.pie(cs, values="count", names=cs.index, title="Call Status Break Down"))                
        #Resources Requested
        cols[0].markdown("### Resources Requested")
        cols[0].bar_chart(rr2) 
        #Prefered Contact Method
        cols[1].plotly_chart(px.pie(rr, values="count", names=rr.index, title="Preferred Contact Method"))                 
        #Resources Requested and Shared
        cols[1].markdown("### Resources Requested and Shared")
        cols[1].bar_chart(rr1) 
        
        #Average call count for completion? this gonna be tricky...
        #Completed Calls 
        cols = st.beta_columns(6)
        for i, df in enumerate(dfs):
            cols[i].markdown(f"#### {df.index.name}")
        for i, df in enumerate(dfs):
            cols[i].bar_chart(df,height=150)
        
        #Email breakdown
       
        
    return 

#maybe sort in render page and then drop duplicates so follow ups get droped?
def render_page(el,cl):
    tenant_details(el,cl) 
    overview(el,cl)
    volunteer_details(cl)    


if __name__ == "__main__":
    creds = st_config()
    el = copy.deepcopy(read_data(creds,"RRT_contacts_cl","Email_log")) #Displays invalid API Key error on web page
    cl = copy.deepcopy(read_data(creds,"RRT_contacts_cl","Call_log"))
    #Credentials check
    if el is not None: render_page(el,cl)
    else: st.text(f"Invalid API key")
