

def llm_response_helper(response) -> str:
    """Convert the llm response to string content"""
    try:
        if isinstance(response, list):
            response_content = response[0].content if response else ""
        elif hasattr(response, "content"):
            response_content = response.content
        else:
            response_content = str(response)
        return response_content
    except Exception as e:
        return "There was an issue processing the llm response"
