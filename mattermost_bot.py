import requests
import schedule
import time
from datetime import datetime
import json
from typing import List, Dict
import logging
import xml.etree.ElementTree as ET
from urllib3.exceptions import InsecureRequestWarning

# Désactive les avertissements SSL
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductManagementBot:
    def __init__(self, webhook_url: str, rss_feeds: List[str]):
        self.webhook_url = webhook_url
        self.rss_feeds = rss_feeds
        
    def parse_rss_content(self, content: str) -> List[Dict]:
        """Parse le contenu XML d'un flux RSS"""
        try:
            root = ET.fromstring(content)
            channel = root.find('channel')
            if channel is None:
                return []
                
            articles = []
            for item in channel.findall('item'):
                title = item.find('title')
                link = item.find('link')
                pubDate = item.find('pubDate')
                
                article = {
                    'title': title.text if title is not None else 'Sans titre',
                    'link': link.text if link is not None else '',
                    'published': pubDate.text if pubDate is not None else datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000'),
                    'source': channel.find('title').text if channel.find('title') is not None else 'Source inconnue'
                }
                articles.append(article)
            
            return articles
        except Exception as e:
            logger.error(f"Erreur lors du parsing XML: {str(e)}")
            return []
        
    def get_articles(self) -> List[Dict]:
        articles = []
        
        for feed_url in self.rss_feeds:
            try:
                logger.info(f"Récupération du flux RSS: {feed_url}")
                
                # Récupère le contenu du flux RSS avec requests
                response = requests.get(feed_url, verify=False, timeout=10)
                response.raise_for_status()
                
                # Parse le contenu XML
                feed_articles = self.parse_rss_content(response.text)
                logger.info(f"Nombre d'articles trouvés pour {feed_url}: {len(feed_articles)}")
                articles.extend(feed_articles)
                
            except Exception as e:
                logger.error(f"Erreur lors de la récupération du flux {feed_url}: {str(e)}")
                continue
        
        logger.info(f"Nombre total d'articles récupérés: {len(articles)}")
        
        try:
            articles.sort(key=lambda x: datetime.strptime(x['published'][:25], '%a, %d %b %Y %H:%M:%S'), reverse=True)
        except Exception as e:
            logger.error(f"Erreur lors du tri des articles: {str(e)}")
            
        return articles[:10]
    
    def format_message(self, articles: List[Dict]) -> str:
        message = "### 📚 Les meilleurs articles Product Management du jour\n\n"
        
        if not articles:
            message += "_Aucun article trouvé aujourd'hui_"
            return message
        
        for article in articles:
            message += f"* [{article['title']}]({article['link']})\n"
            message += f"  _Source: {article['source']}_\n\n"
            
        return message
    
    def post_to_mattermost(self, message: str):
        payload = {
            'text': message,
            'username': 'Product Management Bot',
            'icon_emoji': ':clipboard:'
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                verify=False
            )
            
            if response.status_code != 200:
                logger.error(f"Erreur lors de l'envoi au webhook: {response.status_code}")
                logger.error(f"Réponse: {response.text}")
            else:
                logger.info("Message envoyé avec succès à Mattermost")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du message: {str(e)}")
            
    def daily_update(self):
        logger.info("Début de la mise à jour quotidienne")
        articles = self.get_articles()
        message = self.format_message(articles)
        self.post_to_mattermost(message)
        logger.info("Fin de la mise à jour quotidienne")

# Configuration
RSS_FEEDS = [
    'https://www.mindtheproduct.com/feed/',
    'https://www.producttalk.org/feed/',
    'https://www.productplan.com/feed/',
    'https://www.romanpichler.com/feed/'
]

WEBHOOK_URL = 'https://mattermost.octo.tools/hooks/xhtqrzjonbnjbfwmha6tgangfc'

def main():
    bot = ProductManagementBot(WEBHOOK_URL, RSS_FEEDS)
    
    # Exécute immédiatement une première fois
    logger.info("Première exécution du bot")
    bot.daily_update()
    
    # Programme l'exécution quotidienne
    schedule.every().day.at("09:27").do(bot.daily_update)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()