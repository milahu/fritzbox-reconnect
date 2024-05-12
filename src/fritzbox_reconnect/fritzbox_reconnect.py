#!/usr/bin/env python3

__version__ = "0.0.2"

import os
import sys
import re
import logging
import asyncio



logging_level = "INFO"
#if options.debug:
if True:
    # TODO disable debug log from selenium (too verbose)
    logging_level = "DEBUG"

logging.basicConfig(
    #format='%(asctime)s %(levelname)s %(message)s',
    # also log the logger %(name)s, so we can filter by logger name
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    level=logging_level,
)

logger = logging.getLogger(__name__)

def logger_print(*args):
    logger.debug(" ".join(map(str, args)))



# based on https://stackoverflow.com/a/36077430/10440128
import inspect
async def asyncify(res):
    """
        mix sync and async code.
        f can be sync or async:
        res = await asyncify(f())
    """
    if inspect.isawaitable(res):
        res = await res
    return res



#async def change_ipaddr_fritzbox(self):
async def fritzbox_reconnect(
        base_url="http://192.168.178.1",
        password=None,
        password_file="~/.config/fritzbox_reconnect/password.txt",
        chrome_driver=None,
        chrome_options=None,
        tempdir=None,
    ):

    if not tempdir:
        raise Exception("tempdir is required")

    logger.info(f"using tempdir {tempdir}")

    if not password:
        if password_file.startswith("~/"):
            password_file = os.environ["HOME"] + password_file[1:]
        with open(password_file) as f:
            password = f.read().strip()

    reuse_chrome_driver = chrome_driver != None

    if not chrome_driver:

        # disable debug messages, these are too verbose
        logging.getLogger("websockets.client").setLevel(logging.WARNING)
        logging.getLogger("matplotlib").setLevel(logging.WARNING)

        # https://github.com/kaliiiiiiiiii/Selenium-Driverless
        import selenium_driverless.webdriver as selenium_webdriver
        from selenium_driverless.types.by import By # By.ID, By.XPATH, ...
        # selenium_webdriver.__package__ == "selenium_driverless"
        from selenium_driverless.types.webelement import NoSuchElementException
        from selenium_driverless.types.deserialize import StaleJSRemoteObjReference
        from cdp_socket.exceptions import CDPError
        import cdp_socket

        if not chrome_options:

            chrome_options = selenium_webdriver.ChromeOptions()

            options = chrome_options

            # force dark mode for web contents
            # similar to darkreader extension, but "less dark"?
            options.add_argument("--enable-features=WebContentsForceDark")

            # disable animations like the download animation
            # https://superuser.com/questions/1738597/how-to-disable-all-chromium-animations
            options.add_argument("--wm-window-animations-disabled")
            options.add_argument("--animation-duration-scale=0")

            # dont auto-reload pages on network errors
            # otherwise, switching tabs would reload failed requests
            options.add_argument("--disable-auto-reload")

            options.add_argument(f"--user-data-dir={tempdir}")

            options.add_argument("--window-size=720,480")

            language = "en-US"
            options.add_argument("--lang=%s" % language)

            # Specifies which encryption storage backend to use.
            options.add_argument("--password-store=basic")

            #self._chromium_options = options

        chrome_args = dict(
            options=chrome_options,
        )

        #logger.debug(f"_start_chromium: selenium_webdriver.Chrome")
        driver = await selenium_webdriver.Chrome(**chrome_args)
        #self._driver = driver
        chrome_driver = driver

        # keep this "empty tab" open to keep the window open
        await driver.get("data:text/html,<html><head><title>fritzbox_reconnect</title></head><body><pre>this browser is controlled by fritzbox_reconnect\n\nplease let it run")

    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        base_url = "http://" + base_url

    # open new tab, switch to new tab
    change_ipaddr_window = await asyncify(chrome_driver.switch_to.new_window('tab'))
    #logger_print("new_window_result", repr(new_window_result))

    url = base_url

    async def find_element(*args, **kwargs):
        logger_print(f"change_ipaddr_fritzbox: find_element args={args} kwargs={kwargs}")
        timeout = kwargs.get("timeout", 30)
        kwargs["timeout"] = 5
        # retry loop
        #while True:
        for time_left in range(timeout, 0, -5):
            try:
                return await asyncify(chrome_driver.find_element(*args, **kwargs))
            except NoSuchElementException:
                logger_print(f"change_ipaddr_fritzbox: retrying chrome_driver.find_element")
                pass # retry
        raise TimeoutError

    async def get(self, url: str, referrer: str = None, wait_load: bool = True, timeout: float = 30) -> None:
        """Loads a web page in the current browser session."""
        if "#" in url:
            current_url_base = (await self.current_url).split("#")[0]
            if url[0] == "#":
                # allow to navigate only by fragment ID of the current url
                url = current_url_base + url
                print(f"appending fragement ID to current base url: {url}")
                wait_load = False
            elif url.split("#")[0] == current_url_base:
                # dont wait for fragement-only url change
                print(f"not waiting for fragement-only url change: {url}")
                wait_load = False
        await self.current_target.get(url=url, referrer=referrer, wait_load=wait_load, timeout=timeout)

    chrome_driver.get = get.__get__(chrome_driver)

    while True:
        logger_print(f"change_ipaddr_fritzbox: opening url {url}")
        try:
            # NOTE this can take really long... or even timeout
            # NOTE this can load an empty page
            # when the browser window has no focus
            # chromium seems to give near-zero priority
            # to such background windows
            await asyncify(chrome_driver.get(url, timeout=60))
            logger_print(f"change_ipaddr_fritzbox: opening url: no TimeoutError")
        except TimeoutError:
            logger_print(f"change_ipaddr_fritzbox: opening url: got TimeoutError -> ignoring")
            pass

        logger_print(f"change_ipaddr_fritzbox: entering password")
        try:
            elem = await asyncify(find_element(By.ID, "uiPassInput", timeout=30))
        except TimeoutError:
            logger_print(f"change_ipaddr_fritzbox: entering password: got TimeoutError -> retrying to open url")
            continue
        logger_print(f"change_ipaddr_fritzbox: entering password: elem", elem)
        await asyncify(elem.write(password))

        logger_print(f"change_ipaddr_fritzbox: clicking login")
        elem = await asyncify(find_element(By.ID, "submitLoginBtn", timeout=20))
        logger_print(f"change_ipaddr_fritzbox: clicking login: elem", elem)

        await asyncify(elem.click())

        # NOTE chromium really must run in the foreground of the desktop
        # otherwise it is too slow, and the page will load forever

        logger_print(f"change_ipaddr_fritzbox: waiting for login")
        await asyncio.sleep(20)
        try:
            elem = await asyncify(chrome_driver.find_element(By.ID, "content", timeout=60))
            logger_print(f"change_ipaddr_fritzbox: login done")
            break
        except NoSuchElementException:
            logger_print(f"change_ipaddr_fritzbox: login failed -> retrying")
            # retry

            pass
        except CDPError as e:
            # cdp_socket.exceptions.CDPError: {'code': -32000, 'message': 'Cannot find context with specified id'}
            # selenium_driverless.types.deserialize.StaleJSRemoteObjReference: Page or Frame has been reloaded, or the object deleted, WebElement("HTML>
            logger_print(f"change_ipaddr_fritzbox: login failed: {e} -> ignoring")
            await asyncio.sleep(10)
            break
        except StaleJSRemoteObjReference as e:
            logger_print(f"change_ipaddr_fritzbox: login failed: {e} -> ignoring")
            await asyncio.sleep(10)
            break

    # no. this fails when the window is too small
    # and the menu is hidden

    # we would have to open the menu first
    # by clicking //*[@id="blueBarLogo"]/button
    """
    logger_print(f"change_ipaddr_fritzbox: clicking internet")
    elem = await asyncify(chrome_driver.find_element(By.ID, "inet", timeout=20))
    logger_print(f"change_ipaddr_fritzbox: clicking internet: elem", elem)
    await asyncify(elem.click())
    await asyncio.sleep(5)

    await asyncio.sleep(99999999)

    # FIXME ZeroDivisionError: Weights sum to zero, can't be normalized

    logger_print(f"change_ipaddr_fritzbox: clicking network monitor")
    elem = await asyncify(chrome_driver.find_element(By.ID, "mNetMoni", timeout=20))
    logger_print(f"change_ipaddr_fritzbox: clicking network monitor: elem", elem)
    await asyncify(elem.click())
    await asyncio.sleep(10)
    """

    url = base_url + "/#netMoni"
    #url = "#netMoni"
    logger_print(f"change_ipaddr_fritzbox: opening network monitor page {url}")
    try:
        await asyncify(chrome_driver.get(url, timeout=5))
        logger_print(f"change_ipaddr_fritzbox: no TimeoutError")
    except TimeoutError:
        logger_print(f"change_ipaddr_fritzbox: got TimeoutError -> ignoring")
        pass

    # wait for page load
    # fix: NoSuchElementException
    await asyncio.sleep(5)


    ipaddr_before = None
    ipaddr_after = None

    try:
        # get public IP address
        elem = await asyncify(find_element(By.XPATH, '//*[@id="uiDslIpv4"]/div[3]/div', timeout=10))
        #logger_print(f"change_ipaddr_fritzbox: ipaddr_elem: {elem}")
        ipaddr_text = await asyncify(elem.source)
        #logger_print(f"change_ipaddr_fritzbox: ipaddr_text: {ipaddr_text}")
        ipaddr_before = re.search(r"\d+\.\d+\.\d+\.\d+", ipaddr_text).group(0)
        logger_print(f"change_ipaddr_fritzbox: ipaddr_before: {ipaddr_before}")
    except Exception as e:
        logger_print("change_ipaddr_fritzbox: FIXME Exception", type(e), e)
        await asyncio.sleep(99999)

    while True:

        logger_print(f"change_ipaddr_fritzbox: clicking reconnect")
        elem = await asyncify(find_element(By.ID, "uiReconnectBtn", timeout=20))
        logger_print(f"change_ipaddr_fritzbox: clicking reconnect: elem", elem)
        await asyncify(elem.click())
        # wait for the click
        await asyncio.sleep(5)

        # scroll to the "Internet, IPv4" section
        await chrome_driver.get("#uiDslIpv4")
        # focus works only on input elements
        # https://stackoverflow.com/questions/3656467/is-it-possible-to-focus-on-a-div-using-javascript-focus-function
        """
        elem = await asyncify(find_element(By.ID, "uiDslIpv4", timeout=5))
        # FIXME CDPError: {'code': -32000, 'message': 'Element is not focusable'}
        await asyncify(elem.focus())
        """

        logger_print(f"change_ipaddr_fritzbox: waiting for reconnect")
        await asyncio.sleep(30)

        ipaddr_after = None
        try:
            # get public IP address
            # #uiDslIpv4 > div.flexCell.dyn2 > div
            elem = await asyncify(find_element(By.XPATH, '//*[@id="uiDslIpv4"]/div[3]/div', timeout=120))
            #logger_print(f"change_ipaddr_fritzbox: ipaddr_elem: {elem}")
            ipaddr_text = await asyncify(elem.source)
            #logger_print(f"change_ipaddr_fritzbox: ipaddr_text: {ipaddr_text}")
            ipaddr_after = re.search(r"\d+\.\d+\.\d+\.\d+", ipaddr_text).group(0)
            logger_print(f"change_ipaddr_fritzbox: ipaddr_after: {ipaddr_after}")
        except Exception as e:
            logger_print("change_ipaddr_fritzbox: FIXME Exception", type(e), e)
            await asyncio.sleep(99999)

        if ipaddr_before == ipaddr_after:
            logger_print(f"change_ipaddr_fritzbox: FIXME ipaddr not changed from {ipaddr_before} -> retrying")
            # retry clicking reconnect
            await asyncio.sleep(10)
            continue

        break

    logger_print(f"change_ipaddr_fritzbox: done. changed ipaddr from {ipaddr_before} to {ipaddr_after}")

    # close change_ipaddr_window
    logger_print(f"change_ipaddr_fritzbox: chrome_driver.switch_to.window(change_ipaddr_window)")
    await asyncify(chrome_driver.switch_to.window(change_ipaddr_window))
    await asyncio.sleep(5)

    # close the tab we just used
    logger_print(f"change_ipaddr_fritzbox: chrome_driver.close")
    await asyncify(chrome_driver.close())

    await asyncio.sleep(5)

    #await asyncio.sleep(5)

    # test
    #await asyncio.sleep(9999999)

    # FIXME ConnectionClosedError: sent 1000 (OK); no close frame received

    if not reuse_chrome_driver:
        # close the browser window
        await chrome_driver.quit()

    return (ipaddr_before, ipaddr_after)



def main():

    # register the exit handler only in the main function
    # when fritzbox_reconnect is called from somewhere else
    # then the caller is responsible for cleanup
    import atexit
    atexit.register(exit_handler)

    # TODO argparse sys.argv
    import tempfile
    with tempfile.TemporaryDirectory(prefix="fritzbox_reconnect.") as tempdir:
        asyncio.get_event_loop().run_until_complete(fritzbox_reconnect(
            tempdir=tempdir,
        ))
    return 0



def exit_handler():

    # kill child processes on exit
    import psutil
    current_process = psutil.Process()
    children = current_process.children(recursive=True)
    for child in children:
        try:
            # this can raise psutil.NoSuchProcess
            print(f'exit_handler: killing child process {child.name()} pid {child.pid}')
            child.terminate()
            # TODO wait max 30sec and then child.kill()?
        except Exception as e:
            print(f'exit_handler: killing child process failed: {e}')



if __name__ == "__main__":
    main()
