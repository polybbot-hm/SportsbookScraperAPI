"""Jobs programados (APScheduler). Placeholder: se configurará en main con cron desde config."""
# El scraping periódico se puede añadir en main.py con:
# from apscheduler.schedulers.background import BackgroundScheduler
# scheduler = BackgroundScheduler()
# scheduler.add_job(scraping_job, "cron", **parse_cron(settings.scrape_cron))
# scheduler.start()
# Por ahora sin ejecución automática; el usuario puede llamar a POST /api/v1/scrape
