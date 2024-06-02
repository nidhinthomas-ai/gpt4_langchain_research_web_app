import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="Research Bot")

from langchain_openai import ChatOpenAI
from langchain.utilities import WikipediaAPIWrapper
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.agents import Tool
from langchain.agents import AgentType
from langchain_openai import OpenAIEmbeddings
from langchain import OpenAI
from langchain.agents import initialize_agent
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_community.vectorstores import Chroma
from langchain.chains import VectorDBQA
from langchain_community.tools.uniprot.tool import UniprotQueryRun
from langchain_community.tools.pubmed.tool import PubmedQueryRun
from langchain_community.tools.google_scholar.tool import GoogleScholarQueryRun
from langchain_community.utilities.google_scholar import GoogleScholarAPIWrapper
import sqlite3
import pandas as pd
import os

# Load environment variables from .env file
load_dotenv()

# Sidebar inputs
openai_api_key = st.sidebar.text_input("Enter OpenAI API Key", os.getenv("OPENAI_API_KEY", ""))
serp_api_key = st.sidebar.text_input("Enter SERP API Key", os.getenv("SERP_API_KEY", ""))
temperature = st.sidebar.slider("Temperature", 0.0, 1.0, 0.2)

def create_research_db():
    with sqlite3.connect('MASTER.db') as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Research (
                research_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_input TEXT,
                introduction TEXT,
                quant_facts TEXT,
                publications TEXT,
                books TEXT,
                prev_research TEXT
            )
        """)

def create_messages_db():
    pass

def read_research_table():
    with sqlite3.connect('MASTER.db') as conn:
        query = "SELECT * FROM Research"
        df = pd.read_sql_query(query, conn)
    return df

def insert_research(user_input, introduction, quant_facts, publications, books, prev_research):
    with sqlite3.connect('MASTER.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Research (user_input, introduction, quant_facts, publications, books, prev_research)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_input, introduction, quant_facts, publications, books, prev_research))

def generate_research(userInput):
    global tools
    llm = ChatOpenAI(api_key=openai_api_key, model="gpt-4", temperature=temperature)
    wiki = WikipediaAPIWrapper()
    pubmed = PubmedQueryRun()
    google_scholar = GoogleScholarQueryRun(serp_api_key=serp_api_key)
    uniprot = UniprotQueryRun()

    tools = [
        Tool(
            name="Wikipedia Research Tool",
            func=wiki.run,
            description="Useful for researching information on Wikipedia."
        ),
        Tool(
            name='Pubmed Science and Medical Journal Research Tool',
            func=pubmed.run,
            description='Useful for Pubmed science and medical research\nPubMed comprises more than 35 million citations for biomedical literature from MEDLINE, life science journals, and online books. Citations may include links to full text content from PubMed Central and publisher web sites.'
        ),
        Tool(
            name="Google Scholar Search Tool",
            func=google_scholar.run,
            description="Useful for getting research article hyperlinks from Google Scholar. It can provide links to the articles as well."
        ),
        Tool(
            name="UniProt Protein Information Tool",
            func=uniprot.run,
            description="Useful for getting protein-specific information from UniProt. It can give the function of the protein, organism, amino acid sequence and available PDB structures."
        )
    ]
    if st.session_state.embeddings_db:
        qa = VectorDBQA.from_chain_type(llm=llm, vectorstore=st.session_state.embeddings_db)
        tools.append(
            Tool(
                name='Vector-Based Previous Research Database Tool',
                func=qa.run,
                description='Provides access to previous research results'
            )
        )

    memory = ConversationBufferMemory(memory_key="chat_history")
    runAgent = initialize_agent(
        tools, 
        llm, 
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, 
        verbose=True, 
        memory=memory, 
        handle_parsing_errors=True,
        prefix_prompt="Example responses for each tool:\n"
                      "Wikipedia Research Tool: 'Information about GLP-1 peptide: Glucagon-like peptide-1 (GLP-1) is a 30-amino acid peptide hormone that plays an important role in glucose metabolism.'\n"
                      "UniProt Protein Information Tool: 'Protein details: Name, Function, Organism, PDB structures, Sequence.'\n"
                      "Pubmed Science and Medical Journal Research Tool: 'Recent studies on GLP-1 peptide include... (citation details, brief summary).'\n"
                      "Google Scholar Search Tool: 'Relevant articles for GLP-1 peptide include... (titles and links).'\n"
                      "Ensure all responses are formatted as shown in the examples."
    )

    with st.expander("Generative Results", expanded=True):
        st.subheader("User Input:")
        st.write(userInput)

        st.subheader("Introduction:")
        with st.spinner("Generating Introduction"):
            intro = runAgent({"input": f'Write an academic introduction about {userInput} with at least three paragraphs.'})
            st.write(intro['output'])

        st.subheader("Protein Information from UniProt:")
        with st.spinner("Generating Protein Information"):
            uniprot_info = runAgent({"input": f'''
                Provide detailed information about the protein: "{userInput}" from UniProt including function, organism amino acid sequences, and PDB structures. 
            '''})
            st.write(uniprot_info['output'])

        st.subheader("Quantitative Facts:")
        with st.spinner("Generating Statistical Facts"):
            quantFacts = runAgent({"input": f'''
                Considering user input: {userInput} and the intro paragraph: {intro['output']} 
                \nGenerate a list of 3 to 5 quantitative facts about: {userInput}
                \nOnly return the list of quantitative facts
            '''})
            st.write(quantFacts['output'])

        prev_research = ""
        if st.session_state.embeddings_db:
            st.subheader("Previous Related Research:")
            with st.spinner("Researching Previous Research"):
                qa = VectorDBQA.from_chain_type(llm=llm, vectorstore=st.session_state.embeddings_db)
                prev_research = qa.run({"query": f'''
                    \nReferring to previous results and information, write about: {userInput}
                '''})
                st.write(prev_research)

        st.subheader("Recent Publications:")
        with st.spinner("Generating Recent Publications"):
            papers = runAgent({"input": f'''
                Consider user input: "{userInput}".
                \nConsider the intro paragraph: "{intro['output']}",
                \nConsider these quantitative facts "{quantFacts['output']}"
                \nNow Generate a list of 4 to 5 recent academic papers relating to {userInput}.
                \nInclude Titles, Links to the article, Abstracts. 
            '''})
            st.write(papers['output'])

        st.subheader("Recommended Books:")
        with st.spinner("Generating Recommended Books"):
            readings = runAgent({"input": f'''
                Consider user input: "{userInput}".
                \nConsider the intro paragraph: "{intro['output']}",
                \nConsider these quantitative facts "{quantFacts['output']}"
                \nNow Generate a list of 5 relevant books to read relating to {userInput}.
            '''})
            st.write(readings['output'])

        st.subheader("Research Article Hyperlinks:")
        with st.spinner("Generating Research Article Hyperlinks"):
            google_scholar_links = runAgent({"input": f'''
                Find research articles related to: "{userInput}" on Google Scholar.
                \nProvide titles and working hyperlinks to the articles.
            '''})
            st.write(google_scholar_links['output'])

        insert_research(userInput, intro['output'], quantFacts['output'], papers['output'], readings['output'], prev_research)
        research_text = [userInput, intro['output'], quantFacts['output'], papers['output'], readings['output'], prev_research]
        embedding_function = OpenAIEmbeddings()
        vectordb = Chroma.from_texts(research_text, embedding_function, persist_directory="./chroma_db")
        vectordb.persist()
        st.session_state.embeddings_db = vectordb

class Document:
    def __init__(self, content, topic):
        self.page_content = content
        self.metadata = {"Topic": topic}

def init_ses_states():
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("prev_chat_history", [])
    st.session_state.setdefault("embeddings_db", None)
    st.session_state.setdefault('research', None)
    st.session_state.setdefault("prev_research", None)
    st.session_state.setdefault("books", None)
    st.session_state.setdefault("prev_books", None)

def validate_response(response):
    """
    Validate the response to ensure it has the expected format.
    """
    if 'output' not in response or not response['output']:
        return False
    return True

def chat_with_data(user_message):

    llm = ChatOpenAI(api_key=openai_api_key, model="gpt-4", temperature=temperature)

    wiki = WikipediaAPIWrapper()
    pubmed = PubmedQueryRun()
    google_scholar = GoogleScholarQueryRun(api_wrapper=GoogleScholarAPIWrapper())
    uniprot = UniprotQueryRun()

    tools = [
        Tool(
            name="Wikipedia Research Tool",
            func=wiki.run,
            description="Useful for researching information on Wikipedia"
        ),
        Tool(
            name='Pubmed Science and Medical Journal Research Tool',
            func=pubmed.run,
            description='Useful for Pubmed science and medical research\nPubMed comprises more than 35 million citations for biomedical literature from MEDLINE, life science journals, and online books. Citations may include links to full text content from PubMed Central and publisher web sites.'
        ),
        Tool(
            name="Google Scholar Search Tool",
            func=google_scholar.run,
            description="Useful for getting research article hyperlinks from Google Scholar"
        ),
        Tool(
            name="UniProt Protein Information Tool",
            func=uniprot.run,
            description="Useful for getting protein-specific information from UniProt"
        )
    ]
    if st.session_state.embeddings_db:
        qa = VectorDBQA.from_chain_type(llm=llm, vectorstore=st.session_state.embeddings_db)
        tools.append(
            Tool(
                name='Vector-Based Previous Research Database Tool',
                func=qa.run,
                description='Provides access to previous research results'
            )
        )

    memory = ConversationBufferMemory(memory_key="chat_history")
    chatAgent = initialize_agent(tools, llm, agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION, verbose=True, memory=memory, handle_parsing_errors=True)

    try:
        # Use chatAgent to respond to user message
        response = chatAgent({"input": user_message})

        # Validate the response format
        if not validate_response(response):
            raise ValueError("Invalid response format received from the agent.")

        st.write(response['output'])
    except ValueError as ve:
        st.error(f"ValueError: {ve}")
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Main function to run the Streamlit app
def main():
    create_research_db()
    llm = ChatOpenAI(api_key=openai_api_key, model="gpt-4", temperature=temperature)
    embedding_function = OpenAIEmbeddings()
    init_ses_states()
    if os.path.exists("./chroma_db"):
        st.session_state.embeddings_db = Chroma(persist_directory="./chroma_db", embedding_function=embedding_function)
    st.header("GPT-4o Based Langchain Research Bot")
    deploy_tab, prev_tab = st.tabs(["Generate Research", "Previous Research"])
    with deploy_tab:
        userInput = st.text_area(label="User Input")
        if st.button("Generate Report") and userInput:
            generate_research(userInput)

        st.subheader("Chat with Data")
        user_message = st.text_input(label="User Message", key="um1")
        if st.button("Submit Message") and user_message:
            chat_with_data(user_message)

    with prev_tab:
        st.dataframe(read_research_table())
        selected_input = st.selectbox(label="Previous User Inputs", options=[i for i in read_research_table().user_input])
        if st.button("Render Research") and selected_input:
            with st.expander("Rendered Previous Research", expanded=True):
                selected_df = read_research_table()
                selected_df = selected_df[selected_df.user_input == selected_input].reset_index(drop=True)

                st.subheader("User Input:")
                st.write(selected_df.user_input[0])

                st.subheader("Introduction:")
                st.write(selected_df.introduction[0])

                st.subheader("Quantitative Facts:")
                st.write(selected_df.quant_facts[0])

                st.subheader("Previous Related AI Research:")
                st.write(selected_df.prev_research[0])

                st.subheader("Recent Publications:")
                st.write(selected_df.publications[0])

                st.subheader("Recommended Books:")
                st.write(selected_df.books[0])

if __name__ == '__main__':
    load_dotenv()
    main()
