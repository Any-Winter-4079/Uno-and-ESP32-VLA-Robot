import re
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import urldefrag

load_dotenv()
JINA_API_KEY = os.getenv("JINA_API_KEY") 

#################
# Configuration #
#################

CACHE_FILE_PATH = "browsing_cache.json"
MAX_CACHE_SIZE = 5
MAX_CHUNK_CHARS = 5000

########################
# Helper 1: Load cache #
########################
# NOTE: open_url could fetch a very, very long page. For that reason, we pass the content to the model in chunks of MAX_CHUNK_CHARS,
# and to avoid calling the url again, the full content is cached locally and read from cache, as needed, to be fed to the model
def load_cache():
    if os.path.exists(CACHE_FILE_PATH):
        with open(CACHE_FILE_PATH, 'r') as f:
            return json.load(f)

###########################
# Helper 2: Save to cache #
###########################
# NOTE: keeping a cache begs the question of how many urls to keep content from: the latest MAX_CACHE_SIZE
def save_url_data_to_cache(url, content, cache):
    try:
        # store new content to cache (even if surpassing MAX_CACHE_SIZE)
        cache[url] = {
            "content": content,
            "timestamp": datetime.now().isoformat()
        }

        # sort by datetime
        sorted_cache_items = sorted(
            cache.items(), 
            # item[0], the key ("timestamp")
            # item[1], the value (timestamp)
            key=lambda item: item[1].get("timestamp"), 
            reverse=True
        )
        
        # keep latest MAX_CACHE_SIZE
        cache = {key: value for key, value in sorted_cache_items[:MAX_CACHE_SIZE]}
        
        with open(CACHE_FILE_PATH, 'w') as f:
            json.dump(cache, f, indent=4)
        return True
    
    except Exception as e:
        print(f"save_url_data_to_cache: error: {e}")
        return False

#########################################################################
# Helper 3: Parse Jina search results to obtain url, title, description #
#########################################################################
def parse_jina_search_results(jina_results):
    url_match = re.search(r"URL Source:\s*(.*?)(?=\n\[\d+\]|\n\[\d+\]\s+Description:|\n\[\d+\]\s+Date:|\Z)", jina_results, re.DOTALL)
    title_match = re.search(r"Title:\s*(.*?)(?=\n\[\d+\]|\n\[\d+\]\s+URL Source:|\n\[\d+\]\s+Description:|\Z)", jina_results, re.DOTALL)
    description_match = re.search(r"Description:\s*(.*?)(?=\n\[\d+\]|\n\[\d+\]\s+Date:|\Z)", jina_results, re.DOTALL)
    
    return {
        "url_source": url_match.group(1).strip() if url_match else "Not found",
        "title": title_match.group(1).strip() if title_match else "Not found",
        "description": description_match.group(1).strip() if description_match else "Not found",
    }

#########################################
# Helper 4: Fetch url content with Jina #
#########################################
def fetch_url_content_with_jina(url, timeout=15):    
    try:
        # remove #something from e.g.:
        # https://www.something.com/something#something
        url_without_fragment = urldefrag(url)[0]
        jina_url = f"https://r.jina.ai/{url_without_fragment}"

        response = requests.get(jina_url, timeout=timeout) 
        if response.status_code != 200:
            return None, f"{response.status_code} status code"

        content = response.content.decode('utf-8')

        return content, None
    
    except requests.exceptions.Timeout:
        return None, f"Fetch timeout (timeout={timeout} seconds). Please check your url or set a longer timeout argument if you need to."
    except Exception as e:
        # trim characters
        e = e[10_000:] + "..." if len(e) > 10_000 else e
        return None, e

##############
# Browse web #
##############
def browse_web(browse_query_text, max_results=3, timeout=20):
    try:
        base_url = "https://s.jina.ai/"
        headers = {
            "X-Respond-With": "no-content",
        }
        headers["Authorization"] = f"Bearer {JINA_API_KEY}"

        response = requests.get(base_url, params={"q": browse_query_text}, headers=headers, timeout=timeout)
        if response.status_code != 200:
            return {
                "success": None,
                "error": f"{response.status_code} status code"
            }

        text = response.text.strip()
        pattern = r"\[\d+\]\s+Title:.*?(?=\n\[\d+\]\s+Title:|\Z)"
        matches = re.findall(pattern, text, flags=re.DOTALL)
        
        results = []
        for match in matches[:max_results]:
            results.append(parse_jina_search_results(match))
        
        return {
            "success": results,
            "error": None
        }
    except requests.exceptions.Timeout:
        return {
            "success": None,
            "error": f"Fetch timeout (timeout={timeout} seconds). Please check your query or set a longer timeout argument if you need to."
        }
    except Exception as e:
        e = e[10_000:] + "..." if len(e) > 10_000 else e
        return {
            "success": None,
            "error": e
        }

##################
# Get next chunk #
##################
def get_next_chunk(url, start_char_num, end_char_num, timeout=15):
    try:
        # make sure we don't get more than MAX_CHUNK_CHARS
        end_char_num = min(end_char_num, start_char_num + MAX_CHUNK_CHARS)

        # try to load cache
        content, total_chars = None, None
        cache = load_cache()
        if cache:
            data = cache.get(url)
            if data:
                content = data.get("content")
        else:
            # rewrite the cache (assuming it is empty), risking overwriting existing cache content we may have failed to fetch
            cache = {}
        
        # if no cache hit, fetch again
        if not content:
            content, error = fetch_url_content_with_jina(url, timeout=timeout)
            # if fetch also fails, we return the error
            if not content:
                return {
                    "success": None,
                    "error": f"The content was not found in cache and using Jina resulted in: {error}"
                }
            # update cache
            if not save_url_data_to_cache(url, content, cache):
                print("get_next_chunk: save_url_data_to_cache failed")
        
        # if we have the data (from cache or Jina), get total chars
        total_chars = len(content)
        # make sure we don't pass the final char
        end_char_num = min(total_chars, end_char_num)
        # and get the real chunk to return
        char_chunk = content[start_char_num:end_char_num]
        
        return {
            "success": {
                "content": char_chunk,
                "total_chars": total_chars,
                "range": (start_char_num, end_char_num) # could be shorter than requested
            },
            "error": None
        }

    except Exception as e:
        e = e[10_000:] + "..." if len(e) > 10_000 else e
        return {
            "success": None,
            "error": e
        }

############
# Open url #
############
def open_url(url, timeout=15):
    return get_next_chunk(url, 0, MAX_CHUNK_CHARS, timeout=timeout)

########
# Test #
########
def main():
    query = "NanoGPT speedrun"
    max_results=2

    # browse
    search_results = browse_web(query, max_results=max_results)
    print(search_results)
    print()
    
    if search_results["success"] and len(search_results["success"]) == 2:
        url_1 = search_results["success"][0]["url_source"]
        url_2 = search_results["success"][1]["url_source"]
        
        # open 1st url (fetch (0, MAX_CHUNK_CHARS)), most likely after cache miss
        res_1 = open_url(url_1)
        print(res_1)
        print()
        
        # explore rest of 1st url
        if res_1["success"]:
            total_chars_1 = res_1["success"]["total_chars"]
            current_start_1 = res_1["success"]["range"][1]
            
            while current_start_1 < total_chars_1:
                res_1 = get_next_chunk(url_1, current_start_1, current_start_1 + MAX_CHUNK_CHARS)
                print(res_1)
                print()
                if res_1["error"]:
                    break
                current_start_1 += MAX_CHUNK_CHARS
        
        # move on to 2nd url
        res_2 = open_url(url_2)
        print(res_2)
        print()
        
        # explore rest of 2nd url
        if res_2["success"]:
            total_chars_2 = res_2["success"]["total_chars"]
            current_start_2 = res_2["success"]["range"][1]
            
            while current_start_2 < total_chars_2:
                res_2 = get_next_chunk(url_2, current_start_2, current_start_2 + MAX_CHUNK_CHARS)
                print(res_2)
                print()
                if res_2["error"]:
                    break
                current_start_2 += MAX_CHUNK_CHARS
        
    else:
        print(f"main: browse_web({query}, max_results={max_results}) seems to have failed")

if __name__ == "__main__":
    main()