import re
import random
import logging
import sys
import os
import time
from collections import defaultdict
import concurrent.futures
import yt_dlp

# --- Clean Logging Setup ---
# Configures logging to write to a file and output to the console simultaneously
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("analysis_progress.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

class SilentLogger:
    """Custom logger to mute yt-dlp internal console output and keep logs clean"""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass

# --- Configuration & Speed Settings ---
SAMPLE_SIZE = 40       # Number of random videos to check per year
MAX_THREADS = 4        # Concurrent threads (Keep low to avoid rate-limiting by YouTube)

# Define the browser you use to extract cookies automatically.
# This bypasses age-restrictions and private videos.
# Examples: "chrome", "firefox", "vivaldi", "edge", "brave", "opera", "safari"
BROWSER_NAME = "vivaldi" 

def get_video_duration(url):
    """
    Fetch video duration using yt-dlp.
    Forces the library to ignore format errors (for deleted/unplayable videos)
    and returns the duration directly via a fast flat-extraction.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'ignoreerrors': True,              # Ignore general errors to salvage available data
        'ignore_no_formats_error': True,   # Crucial: bypass format errors and just return duration
        'cookiesfrombrowser': (BROWSER_NAME,),
        'logger': SilentLogger(),
    }
    
    try:
        # Add a slight random delay to avoid rate-limiting (Throttling)
        time.sleep(random.uniform(0.2, 0.8))
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                return info.get('duration', 0)
            return None
    except Exception:
        # Silently skip any unrecoverable errors (e.g., completely deleted videos)
        return None

def main():
    file_path = "watch_history.html"
    logging.info("🚀 Starting YouTube Watch History Analyzer...")
    logging.info("💡 Tip: You can stop the script anytime by pressing Ctrl+C. A partial report will be generated.")
    
    results_summary = []
    total_estimated_hours = 0
    
    try:
        # Read the local Google Takeout HTML file
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # Split the content into individual activity blocks
        blocks = html_content.split('class="content-cell')
        videos_by_year = defaultdict(list)
        
        # Extract YouTube URLs and their corresponding watched year
        for block in blocks:
            if "watch?v=" in block:
                url_match = re.search(r'href="(https://www\.youtube\.com/watch\?v=[^"]+)"', block)
                all_years = re.findall(r'(20\d{2})', block)
                
                if url_match and all_years:
                    url = url_match.group(1)
                    # The last year in the block represents Google's timestamp for the activity
                    year = all_years[-1] 
                    videos_by_year[year].append(url)
                    
        logging.info("✅ Watch history parsed successfully. Starting fast estimation...")
        logging.info("=" * 70)
        
        # Filter valid years (assuming Google Takeout YouTube history structure)
        valid_years = sorted([y for y in videos_by_year.keys() if 2016 <= int(y) <= 2026])
        
        for year in valid_years:
            urls = videos_by_year[year]
            total_videos = len(urls)
            
            if total_videos == 0:
                continue
                
            # Sample random videos to represent the year
            sample_urls = random.sample(urls, min(SAMPLE_SIZE, total_videos))
            total_sample = len(sample_urls)
            
            logging.info(f"📅 [Year {year}] Total videos: {total_videos} | Checking a sample of {total_sample} videos...")
            
            durations = []
            completed_count = 0
            
            # Fetch durations concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                future_to_url = {executor.submit(get_video_duration, url): url for url in sample_urls}
                
                for future in concurrent.futures.as_completed(future_to_url):
                    completed_count += 1
                    duration = future.result()
                    durations.append(duration)
                    
                    if completed_count % 10 == 0 or completed_count == total_sample:
                        logging.info(f"   ➔ Progress in [{year}]: Checked {completed_count}/{total_sample} videos.")
            
            # Filter out invalid durations (deleted or unavailable videos)
            valid_durations = [d for d in durations if d is not None and d > 0]
            
            if valid_durations:
                avg_duration = sum(valid_durations) / len(valid_durations)
                estimated_total_seconds = avg_duration * total_videos
                estimated_hours = estimated_total_seconds / 3600
                total_estimated_hours += estimated_hours
                
                status_text = f"Year {year:<4} ➔ {estimated_hours:.1f} hours (Based on {len(valid_durations)} valid videos)"
                results_summary.append(status_text)
                logging.info(f"✅ Finished {year}: Estimated {estimated_hours:.1f} hours.\n")
            else:
                results_summary.append(f"Year {year:<4} ➔ Could not calculate (All sampled videos are deleted/private)")
                logging.warning(f"⚠️ Could not calculate hours for {year}.\n")

    except KeyboardInterrupt:
        # Handle manual interruption gracefully and generate a partial report
        logging.warning("\n🛑 Script interrupted manually (Ctrl+C)! Generating partial report...")
    except FileNotFoundError:
        logging.error(f"❌ Error: Could not find the file named '{file_path}'. Please ensure it exists in the same directory.")
    except Exception as e:
        logging.error(f"❌ An unexpected error occurred: {e}")
    finally:
        # Print the final or partial report
        if results_summary:
            logging.info("=" * 70)
            logging.info("📊 Final Estimated Report by Year:")
            logging.info("=" * 70)
            for line in results_summary:
                logging.info(line)
            logging.info("=" * 70)
            logging.info(f"🏆 Total Estimated Watch Hours: {total_estimated_hours:.1f} hours.")
            logging.info("=" * 70)

if __name__ == "__main__":
    main()
