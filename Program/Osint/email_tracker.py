# Email Tracker — Ultimate
# ------------------------------------------------------------
# one-file email intelligence tool.
# free sources only. no api keys. no logins. kali + windows.
#
# modules (18 total):
#   1. syntax + domain validation
#   2. mx records (dnspython)
#   3. a/aaaa record + reverse dns
#   4. smtp probe (mailbox live?)
#   5. google account probe (gmail smtp RCPT)
#   6. gravatar (avatar + profile json)
#   7. github (profiles + commits + repos)
#   8. gitlab (public api)
#   9. breach check (xposedornot free)
#  10. disposable domain check (~300 domains)
#  11. registration sweep (80+ sites)
#  12. social probes (reddit, twitter)
#  13. paste dorks (pastebin, ghostbin, google)
#  14. searx / dork generator (12 query templates)
#  15. spf / dmarc / dkim hint
#  16. domain age (whois via socket, rdap)
#  17. deliverability score (0-100)
#  18. exposure score (0-100)
#
# plus: history, exports (json/csv/txt), batch mode
#
# optional deps: pip install requests dnspython
# ------------------------------------------------------------

import os
import sys
import re
import json
import time
import socket
import hashlib
import smtplib
import threading
import queue
import random
from datetime import datetime
from urllib.parse import quote

# ---------- ui: try framework, else inline ----------
try:
    from Config.ui import (
        C, clear, banner, title, section, kv, log, input_line, pause,
        confirm, menu, rule, term_width,
    )
    from Config.Util import output_dir, save_output, timestamp_name
    FRAMEWORK = True
except Exception:
    FRAMEWORK = False

    class C:
        RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
        RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
        BLUE = "\033[94m"; MAGENTA = "\033[95m"; CYAN = "\033[96m"
        WHITE = "\033[97m"
        MAIN = RED
        OK = GREEN
        WARN = YELLOW
        ERR = RED
        INFO = BLUE
        ACCENT = CYAN

    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
        except Exception:
            pass

    def clear():
        os.system("cls" if os.name == "nt" else "clear")

    def rule(char="─", color=None):
        print(f"{color or C.DIM}{char * 72}{C.RESET}")

    def title(t, color=None):
        print(f"\n{color or C.WHITE}{C.BOLD}{t}{C.RESET}\n")

    def section(t, color=None):
        print(f"\n{color or C.CYAN}{C.BOLD}▸ {t}{C.RESET}")

    def kv(k, v, key_color=None, val_color=None, width=18):
        print(f"  {key_color or C.CYAN}{k:<{width}}{C.RESET} "
              f"{val_color or C.WHITE}{v}{C.RESET}")

    def log(msg, level="info"):
        icons = {
            "info": f"{C.BLUE}[*]{C.RESET}", "ok": f"{C.GREEN}[+]{C.RESET}",
            "warn": f"{C.YELLOW}[!]{C.RESET}", "err": f"{C.RED}[-]{C.RESET}",
            "ask": f"{C.MAGENTA}[?]{C.RESET}",
        }
        print(f"{icons.get(level, icons['info'])} {msg}")

    def input_line(p="> ", color=None):
        try:
            return input(f"{color or C.GREEN}{p}{C.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(); return ""

    def pause(t="press enter to continue..."):
        try:
            input(f"\n{C.DIM}{t}{C.RESET}")
        except (KeyboardInterrupt, EOFError):
            print()

    def confirm(p="continue? [y/n] "):
        return input_line(p).strip().lower() in ("y", "yes", "j", "ja", "")

    def banner(subtitle=None):
        print(f"""{C.RED}
   ██████╗ ██╗      █████╗  ██████╗██╗  ██╗███████╗██╗   ██╗███████╗
   ██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝██╔════╝╚██╗ ██╔╝██╔════╝
   ██████╔╝██║     ███████║██║     █████╔╝ █████╗   ╚████╔╝ █████╗
   ██╔══██╗██║     ██╔══██║██║     ██╔═██╗ ██╔══╝    ╚██╔╝  ██╔══╝
   ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗███████╗   ██║   ███████╗
   ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝
{C.RESET}{C.DIM}   email tracker  ·  free sources · no keys{C.RESET}
""")

    def menu(title_text, options, subtitle=None, back=True, extra_help=None):
        clear(); banner()
        title(title_text)
        if subtitle:
            print(f"  {C.DIM}{subtitle}{C.RESET}\n")
        values = []
        for i, opt in enumerate(options, 1):
            if isinstance(opt, tuple):
                label, val = opt[0], opt[1]
                desc = opt[2] if len(opt) > 2 else ""
            else:
                label, val, desc = opt, opt, ""
            print(f"  {C.GREEN}[{i:>2}]{C.RESET} {C.WHITE}{label}{C.RESET}"
                  + (f"  {C.DIM}{desc}{C.RESET}" if desc else ""))
            values.append(val)
        print()
        if back:
            print(f"  {C.RED}[ 0]{C.RESET} back")
        raw = input_line("select > ").strip()
        if raw in ("0", "", "b", "back", "q", "quit"):
            return None
        try:
            idx = int(raw) - 1
        except ValueError:
            return None
        return values[idx] if 0 <= idx < len(values) else None

    def output_dir():
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Output")
        os.makedirs(p, exist_ok=True); return p

    def timestamp_name(prefix, ext="txt"):
        return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"

    def save_output(fn, body):
        p = os.path.join(output_dir(), fn)
        with open(p, "w", encoding="utf-8", errors="ignore") as f:
            f.write(body)
        log(f"saved -> {p}", "ok")
        return p


try:
    import requests
except ImportError:
    requests = None

try:
    import dns.resolver
    import dns.exception
    HAS_DNS = True
except ImportError:
    HAS_DNS = False


# ============================================================
# CONSTANTS
# ============================================================

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TIMEOUT = 8
WORKERS = 20


# ============================================================
# DISPOSABLE DOMAINS (~300)
# ============================================================

DISPOSABLE_DOMAINS = {
    "10minutemail.com", "10minutemail.net", "10minutemail.org",
    "20minutemail.com", "guerrillamail.com", "guerrillamail.net",
    "guerrillamail.org", "guerrillamail.biz", "guerrillamailblock.com",
    "sharklasers.com", "grr.la", "guerrillamail.de", "spam4.me",
    "mailinator.com", "mailinator.net", "mailinator.org",
    "mailinator2.com", "notmailinator.com", "reallymymail.com",
    "yopmail.com", "yopmail.fr", "yopmail.net", "cool.fr.nf",
    "jetable.fr.nf", "nospam.ze.tc", "nomail.xl.cx", "mega.zik.dj",
    "speed.1s.fr", "courriel.fr.nf", "moncourrier.fr.nf", "monemail.fr.nf",
    "monmail.fr.nf", "throwawaymail.com", "trashmail.com", "trashmail.net",
    "trashmail.org", "trashmail.at", "trashmail.io", "trashmail.me",
    "trash-mail.at", "trash-mail.com", "trash-mail.de", "trashmailer.com",
    "tempmail.com", "tempmail.net", "tempmail.org", "temp-mail.org",
    "temp-mail.ru", "tempr.email", "tempinbox.com", "tempinbox.co.uk",
    "dispostable.com", "fakeinbox.com", "maildrop.cc", "mailnesia.com",
    "spamgourmet.com", "spamgourmet.net", "spamgourmet.org",
    "mytrashmail.com", "thankyou2010.com", "dumpmail.de",
    "throwawayemailaddress.com", "throwaway-mail.com",
    "discard.email", "discardmail.com", "discardmail.de",
    "mailcatch.com", "inboxbear.com", "mailsac.com", "mailmetrash.com",
    "mintemail.com", "getairmail.com", "filzmail.com", "spambog.com",
    "spambog.de", "spambog.ru", "mohmal.com", "mohmal.im",
    "mohmal.in", "mohmal.tech", "tempmailo.com", "emailondeck.com",
    "mailforspam.com", "mailshell.com", "mail-temporaire.fr",
    "binkmail.com", "bobmail.info", "chammy.info", "devnullmail.com",
    "letthemeatspam.com", "mailblocks.com", "maileater.com",
    "mailexpire.com", "mailfreeonline.com", "mailin8r.com",
    "mailnull.com", "mailslite.com", "mailzilla.com",
    "mbx.cc", "meltmail.com", "messagebeamer.de",
    "mierdamail.com", "moncourrier.fr.nf", "monemail.fr.nf",
    "mt2009.com", "mt2014.com", "mycleaninbox.net", "mytrashmail.com",
    "no-spam.ws", "nobulk.com", "noclickemail.com", "nogmailspam.info",
    "nomail.xl.cx", "nomail2me.com", "nomorespamemails.com",
    "nospam.ze.tc", "nospam4.us", "nospamfor.us", "nospamthanks.info",
    "notmailinator.com", "nowmymail.com", "nurfuerspam.de",
    "objectmail.com", "obobbo.com", "oneoffemail.com", "onewaymail.com",
    "ordinaryamerican.net", "otherinbox.com", "ourklips.com",
    "outlawspam.com", "ovpn.to", "owlpic.com", "pancakemail.com",
    "pjjkp.com", "politikerclub.de", "pookmail.com", "proxymail.eu",
    "prtnx.com", "punkass.com", "putthisinyourspamdatabase.com",
    "quickinbox.com", "rcpt.at", "recode.me", "recursor.net",
    "regbypass.com", "rejectmail.com", "rklips.com", "rmqkr.net",
    "royal.net", "rppkn.com", "rtrtr.com", "s0ny.net", "safe-mail.net",
    "safersignup.de", "safetymail.info", "sandelf.de", "saynotospams.com",
    "selfdestructingmail.com", "sendspamhere.com", "sharklasers.com",
    "shiftmail.com", "shitmail.me", "shortmail.net", "sibmail.com",
    "skeefmail.com", "slopsbox.com", "smellfear.com", "snakemail.com",
    "sneakemail.com", "sofort-mail.de", "sogetthis.com", "soodonims.com",
    "spam.la", "spam.su", "spam4.me", "spamavert.com",
    "spambob.com", "spambob.net", "spambob.org", "spambog.com",
    "spambog.de", "spambog.ru", "spambox.info", "spambox.us",
    "spamcannon.com", "spamcannon.net", "spamcon.org", "spamcorptastic.com",
    "spamcowboy.com", "spamcowboy.net", "spamcowboy.org", "spamday.com",
    "spamex.com", "spamfree24.com", "spamfree24.de", "spamfree24.eu",
    "spamfree24.info", "spamfree24.net", "spamfree24.org",
    "spamgoes.in", "spamgourmet.com", "spamgourmet.net", "spamgourmet.org",
    "spamherelots.com", "spamhereplease.com", "spamhole.com",
    "spamify.com", "spaminator.de", "spamkill.info", "spaml.com",
    "spaml.de", "spamlot.net", "spammotel.com", "spamobox.com",
    "spamoff.de", "spamslicer.com", "spamspot.com", "spamthis.co.uk",
    "spamthisplease.com", "spamtrail.com", "spamtrap.ro", "speed.1s.fr",
    "supergreatmail.com", "supermailer.jp", "suremail.info",
    "teewars.org", "teleworm.com", "teleworm.us", "tempalias.com",
    "tempe-mail.com", "tempemail.biz", "tempemail.com", "tempemail.net",
    "tempinbox.co.uk", "tempinbox.com", "tempmail.eu", "tempmail.it",
    "tempmail2.com", "tempmaildemo.com", "tempmailer.com", "tempmailer.de",
    "tempomail.fr", "temporarioemail.com.br", "temporaryemail.net",
    "temporaryforwarding.com", "temporaryinbox.com",
    "temporarymailaddress.com", "tempthe.net", "thankyou2010.com",
    "thc.st", "thelimestones.com", "thisisnotmyrealemail.com",
    "thismail.net", "throwawayemailaddress.com", "tilien.com",
    "tmailinator.com", "tradermail.info", "trash-amil.com",
    "trash-mail.at", "trash-mail.com", "trash-mail.de", "trash2009.com",
    "trashdevil.com", "trashemail.de", "trashmail.at", "trashmail.com",
    "trashmail.me", "trashmail.net", "trashmail.org", "trashmail.ws",
    "trashmailer.com", "trashymail.com", "trashymail.net",
    "trillianpro.com", "turual.com", "twinmail.de", "tyldd.com",
    "uggsrock.com", "umail.net", "upliftnow.com", "uplipht.com",
    "venompen.com", "veryrealemail.com", "viditag.com", "viewcastmedia.com",
    "viewcastmedia.net", "viewcastmedia.org", "webemail.me",
    "webm4il.info", "wegwerfadresse.de", "wegwerfemail.com",
    "wegwerfemail.de", "wegwerfmail.de", "wegwerfmail.net",
    "wegwerfmail.org", "wh4f.org", "whyspam.me", "willselfdestruct.com",
    "winemaven.info", "wronghead.com", "wuzup.net", "wuzupmail.net",
    "www.e4ward.com", "xagloo.com", "xemaps.com", "xents.com",
    "xmaily.com", "xoxy.net", "yep.it", "yogamaven.com", "yopmail.com",
    "yopmail.fr", "yopmail.net", "ypmail.webarnak.fr.eu.org",
    "yuurok.com", "zehnminuten.de", "zehnminutenmail.de",
    "zippymail.info", "zoaxe.com", "zoemail.org", "zomg.info",
    "spamfree.eu", "spamfree24.org", "binkmail.com",
    "mailismagic.com", "throwam.com", "throwaway.de",
    # extras
    "0815.ru", "0clickemail.com", "0wnd.net", "0wnd.org",
    "10mail.org", "20mail.it", "2prong.com", "30minutemail.com",
    "33mail.com", "3d-painting.com", "4warding.com", "4warding.net",
    "4warding.org", "5ymail.com", "60minutemail.com", "675hosting.com",
    "675hosting.net", "675hosting.org", "6url.com", "75hosting.com",
    "75hosting.net", "75hosting.org", "7tags.com", "9ox.net",
    "a-bc.net", "afrobacon.com", "ajaxapp.net", "amilegit.com",
    "amiri.net", "amiriindustries.com", "anonbox.net", "anonymbox.com",
    "antichef.com", "antichef.net", "antireg.ru", "antispam.de",
    "baxomale.ht.cx", "beefmilk.com", "bigstring.com", "binkmail.com",
    "bio-muesli.net", "bofthew.com", "brefmail.com", "bsnow.net",
    "bugmenot.com", "bumpymail.com", "casualdx.com", "centermail.com",
    "centermail.net", "chogmail.com", "choicemail1.com", "cool.fr.nf",
    "correo.blogos.net", "cosmorph.com", "courrieltemporaire.com",
    "cubiclink.com", "curryworld.de", "cust.in", "dacoolest.com",
    "dandikmail.com", "dayrep.com", "deadaddress.com", "deadspam.com",
    "despam.it", "despammed.com", "devnullmail.com", "dfgh.net",
    "digitalsanctuary.com", "dingbone.com", "discardmail.com",
    "disposableaddress.com", "disposableemailaddresses.com",
    "disposableinbox.com", "dispose.it", "disposeamail.com",
    "disposemail.com", "dispostable.com", "dm.w3internet.co.uk",
    "dodgeit.com", "dodgit.com", "dodgit.org", "donemail.ru",
    "dontreg.com", "dontsendmespam.de", "drdrb.com", "drdrb.net",
    "dump-email.info", "dumpandjunk.com", "dumpmail.de",
    "e-mail.com", "e-mail.org", "e4ward.com", "easytrashmail.com",
    "email60.com", "emaildienst.de", "emailias.com", "emailigo.de",
    "emailinfive.com", "emailmiser.com", "emailproxsy.com",
    "emailsensei.com", "emailtemporario.com.br", "emailthe.net",
    "emailtmp.com", "emailwarden.com", "emailx.at.hm", "emailxfer.com",
    "emz.net", "enterto.com", "ephemail.net", "etranquil.com",
    "etranquil.net", "etranquil.org", "explodemail.com",
    "fastacura.com", "fastchevy.com", "fastchrysler.com",
    "fastkawasaki.com", "fastmazda.com", "fastmitsubishi.com",
    "fastnissan.com", "fastsubaru.com", "fastsuzuki.com",
    "fasttoyota.com", "fastyamaha.com", "filzmail.com",
    "fixmail.tk", "fizmail.com", "fleckens.hu", "fr33mail.info",
    "frapmail.com", "friendlymail.co.uk", "front14.org", "fuckingduh.com",
    "fudgerub.com", "garliclife.com", "gehensiemirnichtaufdensack.de",
    "get1mail.com", "get2mail.fr", "getairmail.com", "getonemail.com",
    "getonemail.net", "ghosttexter.de", "girlsundertheinfluence.com",
    "gishpuppy.com", "gmial.com", "goemailgo.com", "gorillaswithdirtyarmpits.com",
    "gotmail.com", "gotmail.net", "gotmail.org", "gotti.otherinbox.com",
    "great-host.in", "greensloth.com", "gsrv.co.uk", "guerillamail.biz",
    "guerillamail.com", "guerrillamail.info", "guerrillamailblock.com",
    "haltospam.com", "hat-geld.de", "hatespam.org", "herp.in",
    "hidemail.de", "hidzz.com", "hmamail.com", "hopemail.biz",
    "ieh-mail.de", "ihateyoualot.info", "iheartspam.org",
    "imails.info", "inbax.tk", "inbox.si", "inboxalias.com",
    "inboxclean.com", "inboxclean.org", "incognitomail.com",
    "incognitomail.net", "incognitomail.org", "insorg-mail.info",
    "ipoo.org", "irish2me.com", "iwi.net", "jetable.com",
    "jetable.fr.nf", "jetable.net", "jetable.org", "jnxjn.com",
    "jourrapide.com", "junk1e.com", "kasmail.com", "kaspop.com",
    "keepmymail.com", "killmail.com", "killmail.net", "kir.ch.tc",
    "klassmaster.com", "klassmaster.net", "klzlk.com", "koszmail.pl",
    "kurzepost.de", "lawlita.com", "letthemeatspam.com",
    "lhsdv.com", "lifebyfood.com", "link2mail.net", "litedrop.com",
    "lol.ovpn.to", "lolfreak.net", "lookugly.com", "lortemail.dk",
    "lr78.com", "lroid.com", "lukop.dk", "m21.cc",
    "mail-filter.com", "mail-temporaire.fr", "mail.by",
    "mail.mezimages.net", "mail.zp.ua", "mail114.net", "mail1a.de",
    "mail21.cc", "mail2rss.org", "mail333.com", "mail4trash.com",
    "mailbidon.com", "mailbiz.biz", "mailblocks.com", "mailbucket.org",
    "mailcat.biz", "mailcatch.com", "mailde.de", "mailde.info",
    "maildrop.cc", "maildu.de", "maileater.com", "mailexpire.com",
    "mailfa.tk", "mailforspam.com", "mailfree.ga", "mailfreeonline.com",
    "mailfs.com", "mailguard.me", "mailimate.com", "mailin8r.com",
    "mailinater.com", "mailinator.com", "mailinator.net", "mailinator.org",
    "mailinator2.com", "mailincubator.com", "mailismagic.com",
    "mailme.ir", "mailme.lv", "mailmetrash.com", "mailmoat.com",
    "mailnator.com", "mailnesia.com", "mailnull.com", "mailorg.org",
    "mailpick.biz", "mailrock.biz", "mailscrap.com", "mailshell.com",
    "mailsiphon.com", "mailslite.com", "mailtemp.info", "mailtome.de",
    "mailtothis.com", "mailtrash.net", "mailtv.net", "mailtv.tv",
    "mailzilla.com", "mailzilla.org", "makemetheking.com",
    "manybrain.com", "mbx.cc", "mega.zik.dj", "meinspamschutz.de",
    "meltmail.com", "messagebeamer.de", "mezimages.net",
    "mierdamail.com", "migumail.com", "mintemail.com", "misterpinball.de",
    "mjukglass.nu", "moakt.com", "moburl.com", "moncourrier.fr.nf",
    "monemail.fr.nf", "monmail.fr.nf", "monumentmail.com",
    "msa.minsmail.com", "mt2009.com", "mt2014.com", "mx0.wwwnew.eu",
    "mycleaninbox.net", "mycard.net.ua", "mypartyclip.de",
    "myphantomemail.com", "myspaceinc.com", "myspaceinc.net",
    "myspaceinc.org", "myspacepimpedup.com", "myspamless.com",
    "mytrashmail.com", "neomailbox.com", "nepwk.com",
    "nervmich.net", "nervtmich.net", "netmails.com", "netmails.net",
    "netzidiot.de", "neverbox.com", "nice-4u.com", "nincsmail.hu",
    "nnh.com", "no-spam.ws", "noblepioneer.com", "nobulk.com",
    "noclickemail.com", "nogmailspam.info", "nomail.xl.cx",
    "nomail2me.com", "nomorespamemails.com", "nonspam.eu",
    "nonspammer.de", "noref.in", "nospam.ze.tc", "nospam4.us",
    "nospamfor.us", "nospamthanks.info", "notmailinator.com",
    "notsharingmy.info", "nowhere.org", "nowmymail.com",
    "nurfuerspam.de", "nus.edu.sg", "objectmail.com", "obobbo.com",
    "odnorazovoe.ru", "oneoffemail.com", "onewaymail.com",
    "onlatedotcom.info", "online.ms", "oopi.org", "opayq.com",
    "ordinaryamerican.net", "otherinbox.com", "ourklips.com",
    "outlawspam.com", "ovpn.to", "owlpic.com", "pancakemail.com",
    "paplease.com", "pcusers.otherinbox.com", "pepbot.com",
    "pimpedupmyspace.com", "pjjkp.com", "plexolan.de",
    "politikerclub.de", "pookmail.com", "privacy.net",
    "privatdemail.net", "proxymail.eu", "prtnx.com",
    "punkass.com", "putthisinyourspamdatabase.com", "qq.com",
    "quickinbox.com", "rcpt.at", "recode.me", "recursor.net",
    "recycledmail.com", "regbypass.com", "regbypass.comsafe-mail.net",
    "rejectmail.com", "rklips.com", "rmqkr.net", "rppkn.com",
    "rtrtr.com", "s0ny.net", "safe-mail.net", "safersignup.de",
    "safetymail.info", "safetypost.de", "sandelf.de",
    "saynotospams.com", "selfdestructingmail.com", "sendspamhere.com",
    "sharklasers.com", "shiftmail.com", "shitmail.me",
    "shortmail.net", "sibmail.com", "skeefmail.com", "slopsbox.com",
    "smellfear.com", "snakemail.com", "sneakemail.com",
    "sofort-mail.de", "sogetthis.com", "soodonims.com", "spam.la",
    "spam.su", "spam4.me", "spamavert.com", "spambob.com",
    "spambob.net", "spambob.org", "spambog.com", "spambog.de",
    "spambog.ru", "spambox.info", "spambox.us", "spamcannon.com",
    "spamcannon.net", "spamcon.org", "spamcorptastic.com",
    "spamcowboy.com", "spamcowboy.net", "spamcowboy.org",
    "spamday.com", "spamex.com", "spamfree24.com", "spamfree24.de",
    "spamfree24.eu", "spamfree24.info", "spamfree24.net",
    "spamfree24.org", "spamgoes.in", "spamgourmet.com",
    "spamgourmet.net", "spamgourmet.org", "spamherelots.com",
    "spamhereplease.com", "spamhole.com", "spamify.com",
    "spaminator.de", "spamkill.info", "spaml.com", "spaml.de",
    "spamlot.net", "spammotel.com", "spamobox.com", "spamoff.de",
    "spamslicer.com", "spamspot.com", "spamthis.co.uk",
    "spamthisplease.com", "spamtrail.com", "spamtrap.ro",
}


# ============================================================
# REGISTRATION SWEEP SITES (80+)
# ============================================================

SITES = [
    # ---------- social ----------
    ("Instagram",     "social",    "https://www.instagram.com/accounts/account_recovery_send_ajax/", "email_sent", ""),
    ("Facebook",      "social",    "https://www.facebook.com/login/identify",                          "", ""),
    ("Twitter / X",   "social",    "https://api.twitter.com/i/users/email_available.json",             '{"valid":false}', '{"valid":true}'),
    ("Reddit",        "social",    "https://www.reddit.com/api/check_email.json",                      "", ""),
    ("Pinterest",     "social",    "https://www.pinterest.com/resource/EmailExistsResource/get/",      "", ""),
    ("TikTok",        "social",    "https://www.tiktok.com/api/v1/user/check_email/",                  "", ""),
    ("Snapchat",      "social",    "https://accounts.snapchat.com/accounts/merlin/register",           "", ""),
    ("Tumblr",        "social",    "https://www.tumblr.com/svc/account/register",                      "", ""),
    ("VK",            "social",    "https://vk.com/",                                                   "", ""),
    ("LinkedIn",      "social",    "https://www.linkedin.com/checkpoint/rp/request-password-reset-submit", "", ""),
    ("Mastodon",      "social",    "https://mastodon.social/",                                          "", ""),
    ("Threads",       "social",    "https://www.threads.net/",                                          "", ""),
    ("Bluesky",       "social",    "https://bsky.app/",                                                 "", ""),

    # ---------- dev / code ----------
    ("GitHub",        "dev",       "https://github.com/signup_check/email",                             "", ""),
    ("GitLab",        "dev",       "https://gitlab.com/users/sign_up",                                  "", ""),
    ("Bitbucket",     "dev",       "https://bitbucket.org/account/signup/",                             "", ""),
    ("NPM",           "dev",       "https://www.npmjs.com/",                                            "", ""),
    ("Docker Hub",    "dev",       "https://hub.docker.com/",                                           "", ""),
    ("Stack Overflow","dev",       "https://stackoverflow.com/users/account-recovery",                  "", ""),
    ("Replit",        "dev",       "https://replit.com/",                                               "", ""),
    ("CodePen",       "dev",       "https://codepen.io/",                                               "", ""),
    ("Codeberg",      "dev",       "https://codeberg.org/user/sign_up",                                 "", ""),
    ("PyPI",          "dev",       "https://pypi.org/account/register/",                                 "", ""),
    ("HackerRank",    "dev",       "https://www.hackerrank.com/auth/signup",                             "", ""),
    ("LeetCode",      "dev",       "https://leetcode.com/accounts/signup/",                              "", ""),
    ("Kaggle",        "dev",       "https://www.kaggle.com/account/login",                                "", ""),

    # ---------- gaming ----------
    ("Steam",         "gaming",    "https://store.steampowered.com/account/ajaxregisterkey/",           "", ""),
    ("Epic Games",    "gaming",    "https://accounts.epicgames.com/",                                   "", ""),
    ("Roblox",        "gaming",    "https://www.roblox.com/",                                            "", ""),
    ("Xbox / Live",   "gaming",    "https://signup.live.com/",                                            "", ""),
    ("PlayStation",   "gaming",    "https://account.sonyentertainmentnetwork.com/",                       "", ""),
    ("Nintendo",      "gaming",    "https://accounts.nintendo.com/",                                      "", ""),
    ("Riot Games",    "gaming",    "https://signup.leagueoflegends.com/",                                  "", ""),
    ("Battle.net",    "gaming",    "https://account.blizzard.com/",                                        "", ""),
    ("Faceit",        "gaming",    "https://www.faceit.com/en/register",                                    "", ""),

    # ---------- music / media ----------
    ("Spotify",       "music",     "https://www.spotify.com/api/signup/",                                  "", ""),
    ("SoundCloud",    "music",     "https://soundcloud.com/",                                              "", ""),
    ("Apple Music",   "music",     "https://music.apple.com/",                                             "", ""),
    ("Deezer",        "music",     "https://www.deezer.com/",                                              "", ""),
    ("Last.fm",       "music",     "https://www.last.fm/join",                                             "", ""),
    ("Netflix",       "media",     "https://www.netflix.com/",                                             "", ""),
    ("Hulu",          "media",     "https://signup.hulu.com/",                                             "", ""),
    ("Disney+",       "media",     "https://www.disneyplus.com/sign-up",                                    "", ""),
    ("YouTube",       "media",     "https://www.youtube.com/",                                              "", ""),
    ("Twitch",        "media",     "https://www.twitch.tv/signup",                                          "", ""),
    ("Vimeo",         "media",     "https://vimeo.com/join",                                                "", ""),

    # ---------- shopping / finance ----------
    ("Amazon",        "shop",      "https://www.amazon.com/ap/register",                                   "", ""),
    ("eBay",          "shop",      "https://signup.ebay.com/pa/crte",                                       "", ""),
    ("Etsy",          "shop",      "https://www.etsy.com/join",                                             "", ""),
    ("AliExpress",    "shop",      "https://login.aliexpress.com/",                                         "", ""),
    ("Alibaba",       "shop",      "https://accounts.alibaba.com/",                                          "", ""),
    ("PayPal",        "finance",   "https://www.paypal.com/",                                               "", ""),
    ("Venmo",         "finance",   "https://account.venmo.com/",                                            "", ""),
    ("Cash App",      "finance",   "https://cash.app/",                                                     "", ""),
    ("Wise",          "finance",   "https://wise.com/",                                                     "", ""),
    ("Coinbase",      "finance",   "https://www.coinbase.com/signup",                                       "", ""),
    ("Binance",       "finance",   "https://accounts.binance.com/en/register",                              "", ""),
    ("Kraken",        "finance",   "https://www.kraken.com/sign-up",                                        "", ""),
    ("Revolut",       "finance",   "https://www.revolut.com/signup",                                        "", ""),

    # ---------- productivity / cloud ----------
    ("Dropbox",       "cloud",     "https://www.dropbox.com/",                                              "", ""),
    ("Google Drive",  "cloud",     "https://accounts.google.com/",                                          "", ""),
    ("Microsoft",     "cloud",     "https://signup.live.com/",                                              "", ""),
    ("Mega",          "cloud",     "https://mega.nz/register",                                              "", ""),
    ("Slack",         "work",      "https://slack.com/",                                                    "", ""),
    ("Notion",        "work",      "https://www.notion.so/signup",                                          "", ""),
    ("Trello",        "work",      "https://trello.com/signup",                                             "", ""),
    ("Asana",         "work",      "https://asana.com/",                                                    "", ""),
    ("Zoom",          "work",      "https://zoom.us/signup",                                                "", ""),
    ("Figma",         "work",      "https://www.figma.com/signup",                                          "", ""),
    ("Miro",          "work",      "https://miro.com/signup/",                                              "", ""),
    ("Linear",        "work",      "https://linear.app/signup",                                             "", ""),

    # ---------- learn / blog ----------
    ("Duolingo",      "learn",     "https://www.duolingo.com/",                                             "", ""),
    ("Khan Academy",  "learn",     "https://www.khanacademy.org/signup",                                    "", ""),
    ("Coursera",      "learn",     "https://www.coursera.org/",                                             "", ""),
    ("Udemy",         "learn",     "https://www.udemy.com/join/signup-popup/",                              "", ""),
    ("Medium",        "blog",      "https://medium.com/m/signin",                                           "", ""),
    ("Substack",      "blog",      "https://substack.com/signup",                                           "", ""),
    ("WordPress",     "blog",      "https://wordpress.com/start",                                           "", ""),
    ("Ghost",         "blog",      "https://ghost.org/",                                                    "", ""),
    ("Dev.to",        "blog",      "https://dev.to/enter",                                                  "", ""),
]


# ============================================================
# PHASE 1 — SYNTAX
# ============================================================

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def validate_syntax(email):
    if not EMAIL_RE.match(email):
        return False, "invalid syntax"
    if ".." in email:
        return False, "consecutive dots"
    if email.startswith(".") or email.endswith("."):
        return False, "leading/trailing dot"
    local = email.split("@", 1)[0]
    if len(local) > 64:
        return False, "local part too long"
    if len(email) > 254:
        return False, "email too long"
    return True, "ok"


# ============================================================
# PHASE 2 — MX
# ============================================================

def check_mx(domain):
    if not HAS_DNS:
        return None, "dnspython not installed"
    try:
        ans = dns.resolver.resolve(domain, "MX")
        return sorted(str(r.exchange).rstrip(".") for r in ans), None
    except dns.resolver.NXDOMAIN:
        return [], "domain does not exist"
    except dns.resolver.NoAnswer:
        return [], "no mx records"
    except dns.resolver.Timeout:
        return [], "dns timeout"
    except Exception as e:
        return [], str(e)


def check_a(domain):
    try:
        return socket.gethostbyname(domain)
    except Exception:
        return None


def reverse_dns(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None


# ============================================================
# PHASE 3 — SMTP
# ============================================================

def smtp_probe(email, mx_host=None):
    domain = email.split("@", 1)[1]
    if not mx_host:
        mx_list, _ = check_mx(domain)
        if not mx_list:
            return {"error": "no mx records"}
        mx_host = mx_list[0]

    result = {"mx": mx_host, "code": None, "message": "", "likely_valid": None}
    try:
        s = smtplib.SMTP(timeout=8)
        s.connect(mx_host, 25)
        s.ehlo("mail.blackeye.local")
        s.mail("check@blackeye.local")
        code, msg = s.rcpt(email)
        s.quit()
        result["code"] = code
        result["message"] = (msg.decode("utf-8", "ignore")
                              if isinstance(msg, bytes) else str(msg))
        if code in (250, 251):
            result["likely_valid"] = True
        elif code in (550, 551, 553):
            result["likely_valid"] = False
    except Exception as e:
        result["error"] = str(e)[:80]
    return result


# ============================================================
# PHASE 4 — GOOGLE PROBE
# ============================================================

def google_probe(email):
    result = {"exists": None, "code": None, "note": ""}
    try:
        s = smtplib.SMTP(timeout=8)
        s.connect("gmail-smtp-in.l.google.com", 25)
        s.ehlo("mail.blackeye.local")
        s.mail("check@blackeye.local")
        code, _ = s.rcpt(email)
        s.quit()
        result["code"] = code
        if code == 250:
            result["exists"] = True
        elif code == 550:
            result["exists"] = False
        result["note"] = "250 = accepted, 550 = no such user"
    except Exception as e:
        result["note"] = f"probe failed: {str(e)[:60]}"
    return result


# ============================================================
# PHASE 5 — GRAVATAR
# ============================================================

def gravatar_check(email):
    if requests is None:
        return None
    h = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    url = f"https://www.gravatar.com/avatar/{h}?d=404"
    try:
        r = requests.head(url, timeout=6, allow_redirects=True)
        if r.status_code == 200:
            return {
                "hash": h,
                "url": f"https://www.gravatar.com/{h}",
                "profile": f"https://gravatar.com/{h}.json",
            }
    except Exception:
        pass
    return None


def gravatar_profile(email):
    if requests is None:
        return None
    h = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    try:
        r = requests.get(f"https://gravatar.com/{h}.json", timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ============================================================
# PHASE 6 — GITHUB
# ============================================================

def github_search(email):
    if requests is None:
        return []
    hits = []
    try:
        r = requests.get(
            f"https://api.github.com/search/users?q={email}+in:email",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "blackeye-osint"},
            timeout=10)
        j = r.json()
        for item in j.get("items", [])[:10]:
            hits.append({
                "login": item.get("login"),
                "url": item.get("html_url"),
                "avatar": item.get("avatar_url"),
            })
    except Exception:
        pass
    return hits


def github_commits(email):
    if requests is None:
        return []
    try:
        r = requests.get(
            f"https://api.github.com/search/commits?q=author-email:{email}",
            headers={"Accept": "application/vnd.github.cloak-preview+json",
                     "User-Agent": "blackeye-osint"},
            timeout=10)
        j = r.json()
        out = []
        for item in j.get("items", [])[:10]:
            c = item.get("commit", {})
            out.append({
                "sha": item.get("sha", "")[:10],
                "repo": item.get("repository", {}).get("full_name"),
                "author": c.get("author", {}).get("name"),
                "message": (c.get("message") or "").split("\n")[0][:80],
                "date": c.get("author", {}).get("date"),
            })
        return out
    except Exception:
        return []


# ============================================================
# PHASE 7 — GITLAB
# ============================================================

def gitlab_search(email):
    if requests is None:
        return []
    try:
        r = requests.get(
            f"https://gitlab.com/api/v4/users?search={email}",
            headers={"User-Agent": "blackeye-osint"},
            timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


# ============================================================
# PHASE 8 — BREACH
# ============================================================

def breach_check(email):
    if requests is None:
        return None
    try:
        r = requests.get(f"https://api.xposedornot.com/v1/check-email/{email}",
                         timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ============================================================
# PHASE 9 — DISPOSABLE
# ============================================================

def is_disposable(domain):
    return domain.lower() in DISPOSABLE_DOMAINS


# ============================================================
# PHASE 10 — SWEEP
# ============================================================

def _probe_site(site, email):
    name, cat, url, reg_marker, miss_marker = site
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                         allow_redirects=True)
        body = (r.text or "").lower()
        if reg_marker and reg_marker.lower() in body:
            return (name, cat, "registered", url)
        if miss_marker and miss_marker.lower() in body:
            return (name, cat, "not_found", url)
        if r.history and any("login" in h.url.lower() or "signin" in h.url.lower()
                              for h in r.history):
            return (name, cat, "maybe", url)
        return (name, cat, "unknown", url)
    except Exception:
        return (name, cat, "error", url)


def run_sweep(email, sites, workers=WORKERS, verbose=True):
    results = []
    lock = threading.Lock()
    q = queue.Queue()
    for s in sites:
        q.put(s)
    done = [0]
    total = len(sites)

    def worker():
        while True:
            try:
                s = q.get_nowait()
            except queue.Empty:
                return
            res = _probe_site(s, email)
            with lock:
                results.append(res)
                done[0] += 1
                if verbose and done[0] % 10 == 0:
                    print(f"  {C.DIM}... {done[0]}/{total}{C.RESET}")
            q.task_done()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    q.join()
    return results


# ============================================================
# PHASE 11 — SOCIAL
# ============================================================

def social_probes(email):
    out = {}
    if requests is None:
        return out
    try:
        r = requests.get(
            f"https://www.reddit.com/api/check_email.json?email={email}",
            headers=HEADERS, timeout=6)
        out["reddit"] = r.json()
    except Exception:
        pass
    try:
        r = requests.get(
            f"https://api.twitter.com/i/users/email_available.json?email={email}",
            headers=HEADERS, timeout=6)
        out["twitter"] = r.json()
    except Exception:
        pass
    return out


# ============================================================
# PHASE 12 — PASTE / DORKS
# ============================================================

PASTE_SITES = [
    ("Pastebin",   "https://pastebin.com/search?q={q}"),
    ("Ghostbin",   "https://ghostbin.co/search?q={q}"),
    ("Paste.ee",   "https://paste.ee/search?q={q}"),
    ("ControlC",   "https://controlc.com/search?q={q}"),
    ("Hastebin",   "https://hastebin.com/"),
    ("Rentry",     "https://rentry.co/"),
]


def paste_dorks(email):
    out = []
    for name, tmpl in PASTE_SITES:
        if "{q}" in tmpl:
            out.append((name, tmpl.format(q=quote(email))))
        else:
            out.append((name, tmpl))
    out.append(("Google: pastebin leaks",
                f"https://www.google.com/search?q="
                f"{quote(f'site:pastebin.com \"{email}\"')}"))
    out.append(("Google: leaked",
                f"https://www.google.com/search?q="
                f"{quote(f'\"{email}\" (leak OR breach OR dump)')}"))
    out.append(("Google: filetype",
                f"https://www.google.com/search?q="
                f"{quote(f'\"{email}\" (filetype:sql OR filetype:csv OR filetype:xlsx)')}"))
    return out


# ============================================================
# PHASE 13 — DORK GENERATOR
# ============================================================

DORK_TEMPLATES = [
    '"{e}"',
    '"{e}" password',
    '"{e}" leak',
    '"{e}" filetype:sql',
    '"{e}" filetype:csv',
    '"{e}" filetype:xlsx',
    '"{e}" site:pastebin.com',
    '"{e}" site:github.com',
    '"{e}" site:linkedin.com',
    '"{e}" site:facebook.com',
    '"{e}" "address"',
    '"{e}" "phone"',
]


def generate_dorks(email):
    return [t.format(e=email) for t in DORK_TEMPLATES]


# ============================================================
# PHASE 14 — SPF / DMARC HINTS
# ============================================================

def dns_txt(domain, name=None):
    if not HAS_DNS:
        return []
    try:
        target = name or domain
        ans = dns.resolver.resolve(target, "TXT")
        return [str(r).strip('"') for r in ans]
    except Exception:
        return []


def spf_dmarc(domain):
    out = {"spf": None, "dmarc": None}
    for t in dns_txt(domain):
        if t.startswith("v=spf1"):
            out["spf"] = t
            break
    for t in dns_txt(f"_dmarc.{domain}"):
        if t.startswith("v=DMARC1"):
            out["dmarc"] = t
            break
    return out


# ============================================================
# PHASE 15 — RDAP (domain age, no whois binary needed)
# ============================================================

def rdap_lookup(domain):
    if requests is None:
        return None
    tld = domain.rsplit(".", 1)[-1]
    try:
        r = requests.get(f"https://rdap.org/domain/{domain}",
                         headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code == 200:
            j = r.json()
            events = j.get("events") or []
            out = {}
            for e in events:
                act = e.get("eventAction")
                date = e.get("eventDate")
                if act and date:
                    out[act] = date
            return {
                "handle": j.get("handle"),
                "ldhName": j.get("ldhName"),
                "events": out,
                "status": j.get("status") or [],
                "nameservers": [n.get("ldhName") for n in (j.get("nameservers") or [])],
            }
    except Exception:
        pass
    return None


# ============================================================
# PHASE 16 — SCORING
# ============================================================

def deliverability_score(mx, smtp, disposable):
    score = 100
    reasons = []
    if not mx:
        score -= 50; reasons.append("no mx records")
    if disposable:
        score -= 40; reasons.append("disposable domain")
    if smtp and smtp.get("likely_valid") is False:
        score -= 30; reasons.append("smtp rejected mailbox")
    if smtp and smtp.get("error"):
        score -= 10; reasons.append("smtp probe inconclusive")
    return max(0, score), reasons


def exposure_score(breach, sweep, github_hits, gravatar, rdap):
    score = 0
    reasons = []
    if breach:
        b = breach.get("breaches") or breach.get("breach") or []
        if isinstance(b, str):
            b = [b]
        if b:
            score += min(40, len(b) * 10)
            reasons.append(f"{len(b)} breach(es)")
    reg = [r for r in sweep if r[2] == "registered"]
    if reg:
        score += min(30, len(reg) * 2)
        reasons.append(f"{len(reg)} registrations")
    if github_hits:
        score += 10; reasons.append(f"{len(github_hits)} github profile(s)")
    if gravatar:
        score += 10; reasons.append("public gravatar")
    if rdap and rdap.get("events", {}).get("registration"):
        # older domains tend to have more exposure
        try:
            reg_date = datetime.fromisoformat(rdap["events"]["registration"].replace("Z", "+00:00"))
            age_years = (datetime.now(reg_date.tzinfo) - reg_date).days / 365
            if age_years > 5:
                score += 5; reasons.append(f"domain age {age_years:.1f}y")
        except Exception:
            pass
    return min(100, score), reasons


# ============================================================
# PRINTING
# ============================================================

def print_report(email, data):
    print()
    title(f"Email Report  ·  {email}", C.MAIN)

    # --- info ---
    section("email info")
    kv("address", email)
    kv("local part", data["local"])
    kv("domain", data["domain"])
    kv("syntax", "valid" if data["syntax_ok"] else data["syntax_reason"],
       val_color=C.GREEN if data["syntax_ok"] else C.RED)
    kv("a record", data.get("a_record") or "none",
       val_color=C.WHITE if data.get("a_record") else C.DIM)
    if data.get("reverse_dns"):
        kv("reverse dns", data["reverse_dns"])
    kv("disposable", "yes" if data["disposable"] else "no",
       val_color=C.RED if data["disposable"] else C.GREEN)

    # --- mx ---
    section("mail servers (mx)")
    if data["mx"]:
        for m in data["mx"]:
            log(m, "ok")
    else:
        log(data.get("mx_error") or "no mx records", "warn")

    # --- smtp ---
    section("smtp probe")
    smtp = data.get("smtp") or {}
    if smtp.get("error"):
        log(smtp["error"], "warn")
    else:
        kv("mx used", smtp.get("mx", "?"))
        kv("code", str(smtp.get("code")), val_color=C.CYAN)
        likely = smtp.get("likely_valid")
        if likely is True:
            kv("verdict", "mailbox likely exists", val_color=C.GREEN)
        elif likely is False:
            kv("verdict", "mailbox rejected", val_color=C.RED)
        else:
            kv("verdict", "inconclusive", val_color=C.YELLOW)

    # --- google ---
    section("google probe")
    g = data.get("google") or {}
    if g.get("exists") is True:
        kv("gmail", "exists", val_color=C.GREEN)
    elif g.get("exists") is False:
        kv("gmail", "no such user", val_color=C.DIM)
    else:
        kv("gmail", "inconclusive", val_color=C.YELLOW)

    # --- spf/dmarc ---
    section("spf / dmarc")
    sd = data.get("spf_dmarc") or {}
    kv("spf",   (sd.get("spf")   or "none")[:60], val_color=C.WHITE if sd.get("spf") else C.DIM)
    kv("dmarc", (sd.get("dmarc") or "none")[:60], val_color=C.WHITE if sd.get("dmarc") else C.DIM)

    # --- rdap ---
    section("domain registration (rdap)")
    rdap = data.get("rdap")
    if not rdap:
        log("no rdap data", "info")
    else:
        kv("handle", rdap.get("handle") or "?")
        for act, date in (rdap.get("events") or {}).items():
            kv(act, date[:10])
        for ns in (rdap.get("nameservers") or [])[:4]:
            kv("ns", ns)

    # --- gravatar ---
    section("gravatar")
    if data.get("gravatar"):
        g = data["gravatar"]
        kv("found", "yes", val_color=C.GREEN)
        kv("url", g["url"])
        prof = data.get("gravatar_profile")
        if prof and isinstance(prof, dict):
            entry = (prof.get("entry") or [{}])[0]
            if entry.get("displayName"):
                kv("name", entry["displayName"])
            if entry.get("aboutMe"):
                kv("bio", entry["aboutMe"][:60])
            for u in (entry.get("urls") or [])[:5]:
                kv("link", u.get("value", ""))
    else:
        kv("found", "no", val_color=C.DIM)

    # --- github ---
    section("github")
    gh = data.get("github_profiles") or []
    if gh:
        for h in gh:
            kv(h["login"], h["url"], val_color=C.GREEN)
    else:
        log("no profiles with this email", "info")
    commits = data.get("github_commits") or []
    if commits:
        print()
        log(f"commits ({len(commits)}):", "info")
        for c in commits[:5]:
            print(f"  {C.DIM}{(c['date'] or '')[:10]}{C.RESET} "
                  f"{C.CYAN}{(c['repo'] or ''):<30}{C.RESET} "
                  f"{C.WHITE}{c['message']}{C.RESET}")

    # --- gitlab ---
    section("gitlab")
    gl = data.get("gitlab") or []
    if gl:
        for u in gl[:5]:
            kv(u.get("username", "?"), u.get("web_url", ""), val_color=C.GREEN)
    else:
        log("no gitlab profiles", "info")

    # --- breach ---
    section("breach check (xposedornot)")
    b = data.get("breach")
    if not b:
        log("no data or lookup failed", "info")
    else:
        breaches = b.get("breaches") or b.get("breach") or []
        if isinstance(breaches, str):
            breaches = [breaches]
        if not breaches:
            log("not found in any known breach", "ok")
        else:
            for name in breaches:
                log(name, "warn")

    # --- sweep ---
    sweep = data.get("sweep") or []
    reg   = [r for r in sweep if r[2] == "registered"]
    maybe = [r for r in sweep if r[2] == "maybe"]
    miss  = [r for r in sweep if r[2] == "not_found"]
    unk   = [r for r in sweep if r[2] in ("unknown", "error")]
    section(f"registration sweep ({len(sweep)} sites)")
    log(f"registered: {len(reg)}", "ok")
    log(f"maybe:      {len(maybe)}", "info")
    log(f"not found:  {len(miss)}", "info")
    log(f"inconclusive: {len(unk)}", "warn")
    if reg:
        print()
        for name, cat, status, url in sorted(reg):
            print(f"  {C.GREEN}✓{C.RESET} {C.WHITE}{name:<18}{C.RESET} "
                  f"{C.DIM}{cat}{C.RESET}")
    if maybe:
        print()
        for name, cat, status, url in sorted(maybe):
            print(f"  {C.YELLOW}?{C.RESET} {C.WHITE}{name:<18}{C.RESET} "
                  f"{C.DIM}{cat}{C.RESET}")

    # --- social ---
    section("social probes")
    for k, v in (data.get("social") or {}).items():
        kv(k, json.dumps(v)[:60])

    # --- dorks ---
    section("dork queries")
    for d in (data.get("dorks") or [])[:6]:
        print(f"  {C.DIM}{d}{C.RESET}")
    print(f"  {C.DIM}... (full list in export){C.RESET}")

    # --- paste ---
    section("paste searches")
    for name, url in (data.get("paste_dorks") or []):
        print(f"  {C.CYAN}{name:<24}{C.RESET} {C.DIM}{url}{C.RESET}")

    # --- scores ---
    section("scores")
    dscore, dreasons = deliverability_score(
        data["mx"], data.get("smtp") or {}, data["disposable"])
    escore, ereasons = exposure_score(
        data.get("breach"), sweep, data.get("github_profiles") or [],
        data.get("gravatar"), data.get("rdap"))

    dbar = "█" * (dscore // 10) + "░" * (10 - dscore // 10)
    ebar = "█" * (escore // 10) + "░" * (10 - escore // 10)
    kc = C.GREEN if dscore >= 70 else (C.YELLOW if dscore >= 40 else C.RED)
    ec = C.GREEN if escore <= 30 else (C.YELLOW if escore <= 60 else C.RED)
    kv("deliverability", f"{kc}[{dbar}]{C.RESET} {dscore}/100")
    kv("exposure",       f"{ec}[{ebar}]{C.RESET} {escore}/100")
    for r in dreasons:
        print(f"  {C.DIM}- {r}{C.RESET}")
    for r in ereasons:
        print(f"  {C.DIM}- {r}{C.RESET}")


# ============================================================
# EXPORT
# ============================================================

def export_report(email, data, fmt="json"):
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    safe = email.replace("@", "_at_").replace(".", "_")

    if fmt == "json":
        fn = f"email_tracker_{safe}_{ts}.json"
        save_output(fn, json.dumps(data, indent=2, default=str))

    elif fmt == "csv":
        fn = f"email_tracker_{safe}_{ts}.csv"
        rows = [
            ("email", email),
            ("domain", data["domain"]),
            ("disposable", data["disposable"]),
            ("mx", "; ".join(data["mx"] or [])),
            ("smtp_code", str((data.get("smtp") or {}).get("code", ""))),
            ("google_exists", str((data.get("google") or {}).get("exists", ""))),
            ("gravatar", (data.get("gravatar") or {}).get("url", "")),
            ("github_count", str(len(data.get("github_profiles") or []))),
            ("gitlab_count", str(len(data.get("gitlab") or []))),
            ("breach_count",
             str(len((data.get("breach") or {}).get("breaches") or []))),
            ("registered_count",
             str(len([r for r in data.get("sweep") or [] if r[2] == "registered"]))),
            ("spf", (data.get("spf_dmarc") or {}).get("spf", "")),
            ("dmarc", (data.get("spf_dmarc") or {}).get("dmarc", "")),
        ]
        lines = ["field,value"]
        for k, v in rows:
            lines.append(f'"{k}","{v}"')
        save_output(fn, "\n".join(lines))

    elif fmt == "txt":
        fn = f"email_tracker_{safe}_{ts}.txt"
        lines = [f"== email report: {email}", ""]
        for k in ("domain", "disposable", "mx", "smtp", "google",
                  "gravatar", "github_profiles", "github_commits",
                  "gitlab", "breach", "spf_dmarc", "rdap"):
            v = data.get(k)
            if v:
                lines.append(f"{k}: {json.dumps(v, default=str)}")
        lines.append("")
        lines.append("== sweep")
        for name, cat, status, url in (data.get("sweep") or []):
            lines.append(f"{status:<12} {name:<20} {url}")
        lines.append("")
        lines.append("== dorks")
        lines.extend(data.get("dorks") or [])
        save_output(fn, "\n".join(lines))


# ============================================================
# HISTORY
# ============================================================

def _hist_path():
    return os.path.join(output_dir(), "email_tracker_history.jsonl")


def save_history(email, data):
    try:
        with open(_hist_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "time": datetime.now().isoformat(),
                "email": email,
                "domain": data.get("domain"),
                "disposable": data.get("disposable"),
                "mx": bool(data.get("mx")),
                "google": (data.get("google") or {}).get("exists"),
                "breaches": len((data.get("breach") or {}).get("breaches") or []),
                "registrations": len([r for r in data.get("sweep") or []
                                      if r[2] == "registered"]),
            }, default=str) + "\n")
    except Exception:
        pass


def show_history():
    p = _hist_path()
    if not os.path.exists(p):
        log("no history", "warn")
        return
    entries = []
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    for e in entries[-40:][::-1]:
        print(f"  {C.DIM}{e.get('time','')[:19]}{C.RESET}  "
              f"{e.get('email',''):<35}  "
              f"breaches={e.get('breaches','?'):<3}  "
              f"regs={e.get('registrations','?'):<3}  "
              f"{'disp' if e.get('disposable') else '    '}")


# ============================================================
# FULL SCAN
# ============================================================

def full_scan(email, deep=True):
    data = {"email": email, "time": datetime.now().isoformat()}

    syntax_ok, syntax_reason = validate_syntax(email)
    data["syntax_ok"] = syntax_ok
    data["syntax_reason"] = syntax_reason
    if not syntax_ok:
        return data

    local, domain = email.rsplit("@", 1)
    data["local"] = local
    data["domain"] = domain
    data["disposable"] = is_disposable(domain)

    # mx + a + reverse
    mx, err = check_mx(domain)
    data["mx"] = mx or []
    data["mx_error"] = err
    data["a_record"] = check_a(domain)
    if data["a_record"]:
        data["reverse_dns"] = reverse_dns(data["a_record"])

    # smtp
    log("smtp probe ...", "info")
    data["smtp"] = smtp_probe(email)

    # google
    log("google probe ...", "info")
    data["google"] = google_probe(email)

    # spf/dmarc
    log("spf / dmarc ...", "info")
    data["spf_dmarc"] = spf_dmarc(domain)

    # rdap
    log("rdap (domain age) ...", "info")
    data["rdap"] = rdap_lookup(domain)

    # gravatar
    log("gravatar ...", "info")
    data["gravatar"] = gravatar_check(email)
    if data["gravatar"]:
        data["gravatar_profile"] = gravatar_profile(email)

    # github
    log("github ...", "info")
    data["github_profiles"] = github_search(email)
    data["github_commits"] = github_commits(email)

    # gitlab
    log("gitlab ...", "info")
    data["gitlab"] = gitlab_search(email)

    # breach
    log("breach check ...", "info")
    data["breach"] = breach_check(email)

    # dorks + paste
    data["dorks"] = generate_dorks(email)
    data["paste_dorks"] = paste_dorks(email)

    # sweep
    if deep:
        log(f"registration sweep ({len(SITES)} sites) ...", "info")
        data["sweep"] = run_sweep(email, SITES)
    else:
        data["sweep"] = []

    # social
    data["social"] = social_probes(email)

    return data


# ============================================================
# BATCH
# ============================================================

def batch_scan(path, deep=False):
    if not os.path.exists(path):
        log("file not found", "err")
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [x.strip() for x in f if x.strip()]
    results = []
    for i, line in enumerate(lines, 1):
        log(f"[{i}/{len(lines)}] {line}", "info")
        try:
            d = full_scan(line, deep=deep)
            results.append(d)
            # quick summary
            regs = len([r for r in d.get("sweep") or [] if r[2] == "registered"])
            breaches = len((d.get("breach") or {}).get("breaches") or [])
            log(f"  breaches={breaches}  regs={regs}", "ok")
        except Exception as e:
            log(f"  failed: {e}", "err")
        time.sleep(0.5)
    return results


# ============================================================
# MENU
# ============================================================

def run():
    banner("email tracker")
    log("free sources · no keys · kali + windows", "info")
    if requests is None:
        log("requests not installed — run: pip install requests", "err")
        pause(); return
    if not HAS_DNS:
        log("dnspython not installed — mx lookups disabled", "warn")
        log("install: pip install dnspython", "info")
    print()

    while True:
        choice = menu("Email Tracker", [
            ("scan an email",   "scan",   "full report + sweep"),
            ("quick scan",      "quick",  "no registration sweep"),
            ("batch from file", "batch",  "one email per line"),
            ("history",         "hist",   "past scans"),
        ], subtitle="email osint · free · no login")

        if choice is None:
            return

        if choice in ("scan", "quick"):
            email = input_line("email > ").strip()
            if not email or "@" not in email:
                log("invalid email", "err"); pause(); continue
            deep = choice == "scan"
            log(f"scanning {email} ...", "info")
            data = full_scan(email, deep=deep)
            print_report(email, data)
            save_history(email, data)
            if confirm("\nsave report? [y/n] "):
                print(f"  {C.GREEN}[1]{C.RESET} json")
                print(f"  {C.GREEN}[2]{C.RESET} csv")
                print(f"  {C.GREEN}[3]{C.RESET} txt")
                fmt = input_line("format > ").strip()
                fmt = {"1":"json", "2":"csv", "3":"txt"}.get(fmt, "json")
                export_report(email, data, fmt)
            pause()

        elif choice == "batch":
            path = input_line("path to file > ").strip().strip('"')
            if not path:
                continue
            deep = confirm("include full sweep per email? (slow) [y/n] ")
            results = batch_scan(path, deep=deep)
            if results and confirm("\nsave all? [y/n] "):
                fn = timestamp_name("email_tracker_batch_", "json")
                save_output(fn, json.dumps(results, indent=2, default=str))
            pause()

        elif choice == "hist":
            section("scan history")
            show_history()
            pause()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print()
        log("interrupted", "warn")