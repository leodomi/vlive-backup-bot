# -*- coding: utf-8 -*-
from collections import deque
import time
import re
import os
from webbrowser import open_new_tab

from bs4 import BeautifulSoup, element
import requests
import reqWrapper
import vlivepy
import vlivepy.board
import vlivepy.parser
import vlivepy.variables
from vlivepy.parser import format_epoch
from prompt_toolkit import (
    PromptSession,
)
from prompt_toolkit.shortcuts import (
    set_title,
    message_dialog,
    input_dialog,
    button_dialog,
    progress_dialog,
    checkboxlist_dialog,
    clear,
)
import pyclip

__version__ = "0.2.0"

set_title("VLIVE-BACKUP-BOT")
ptk_session = PromptSession()
vlivepy.variables.override_gcc = "US"


def dialog_splash():
    has_update = False
    zipball = None
    info_url = None

    def callback_fn(report_progress, report_log):
        nonlocal has_update
        nonlocal zipball
        nonlocal info_url
        report_progress(0)
        content = rf"""

██╗   ██╗██╗     ██╗██╗   ██╗███████╗            
██║   ██║██║     ██║██║   ██║██╔════╝            
██║   ██║██║     ██║██║   ██║█████╗              
╚██╗ ██╔╝██║     ██║╚██╗ ██╔╝██╔══╝              
 ╚████╔╝ ███████╗██║ ╚████╔╝ ███████╗            
  ╚═══╝  ╚══════╝╚═╝  ╚═══╝  ╚══════╝            
                                                 
██████╗  █████╗  ██████╗██╗  ██╗██╗   ██╗██████╗ 
██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██║   ██║██╔══██╗
██████╔╝███████║██║     █████╔╝ ██║   ██║██████╔╝
██╔══██╗██╔══██║██║     ██╔═██╗ ██║   ██║██╔═══╝ 
██████╔╝██║  ██║╚██████╗██║  ██╗╚██████╔╝██║     
╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     
                                                 
██████╗  ██████╗ ████████╗                       
██╔══██╗██╔═══██╗╚══██╔══╝                       
██████╔╝██║   ██║   ██║                          
██╔══██╗██║   ██║   ██║                          
██████╔╝╚██████╔╝   ██║     VER {__version__}                 
╚═════╝  ╚═════╝    ╚═╝     by @box_archived                
"""
        report_log(content)

        time.sleep(1)

        report_progress(50)
        report_log("\n Checking for updates...")
        sr = reqWrapper.get("https://api.github.com/repos/box-archived/vlive-backup-bot/releases/latest", status=[200])
        if sr.success:
            release_data = sr.response.json()
            latest = release_data['tag_name'][1:]
            if __version__ != latest:
                has_update = True
                zipball = release_data["zipball_url"]
                info_url = release_data["html_url"]

        time.sleep(1)
        report_progress(100)

    progress_dialog(
        title="VLIVE-BACKUP-BOT",
        text="",
        run_callback=callback_fn,
    ).run()

    return has_update, zipball, info_url


def tool_format_creator(max_int):
    max_len = len(str(max_int))
    return "%%%dd/%%%dd" % (max_len, max_len)


def tool_remove_emoji(plain_text, sub, allow_emoji=False):
    uni_emoji = ""
    if allow_emoji:
        uni_emoji = "\U0001F1E0-\U0001FAFF\U00002702-\U000027B0"
    emoji_regex = re.compile(
        r"([^"
        "\u0020-\u007e"  # 기본 문자
        # "\u0080-\u024f"  # 라틴 기본
        "\u1100-\u11ff"  # 한글 자모
        "\u3131-\u318f"  # 호환용 한글
        "\uac00-\ud7a3"  # 한글 음절
        "\u3040-\u309f"  # 히라가나
        "\u30a0-\u30ff"  # 가타카나
        "\u2e80-\u2eff"  # CJK 부수보충
        "\u4e00-\u9fbf"  # CJK 통합 한자
        "\u3400-\u4dbf"  # CJK 통합 한자 확장 - A
        f"{uni_emoji}"
        "])"
    )

    if allow_emoji:
        return emoji_regex.sub(sub, plain_text)
    else:
        return emoji_regex.sub(sub, plain_text).encode("cp949", "ignore").decode("cp949")


def tool_clip_text_length(plain_text, length):
    if len(plain_text) > length:
        plain_text = plain_text[:length-3] + ".._"

    return plain_text


def tool_regex_window_name(plain_text):
    # remove front space
    regex_front_space = re.compile(r"^(\s+)")
    regex_window_name = re.compile(r'[<>:"\\/|?*~%]')

    safe_name = regex_window_name.sub("_", regex_front_space.sub("", plain_text))

    return safe_name


def tool_calc_percent(full, now):
    res = now / full * 100
    if res >= 100:
        res -= 1
    return res


def tool_parse_url(url: str):
    # pa`rse extension
    ext_split = url.split("?")[0].rsplit(".", 1)

    # parse server filename
    filename = ext_split[0].rsplit("/", 1)[-1]

    return ext_split[-1], filename


def tool_max_len_filename(location, filename, ext):
    avail_length = 255 - len(location) - len(ext) - 2
    return tool_clip_text_length(filename, avail_length)


def tool_download_file(url: str, location: str, filename: str = None,):
    headers = {**vlivepy.variables.HeaderCommon}
    filename = tool_regex_window_name(filename)
    ext, name = tool_parse_url(url)

    if filename is None:
        filename = name

    alter = name

    def do_download():
        nonlocal url, location, filename, alter, headers, ext

        filename = tool_max_len_filename(location, filename, ext)

        with requests.get(url, stream=True, headers=headers) as r:
            r.raise_for_status()
            with open(f"{location}/{filename}.{ext}", 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return True

    # create dir
    os.makedirs(location, exist_ok=True)
    try:
        return do_download()
    except OSError:
        filename = alter
        try:
            do_download()
        except:
            return False
    except:
        return False


def proc_redundant_download(url: str, location: str, filename: str = None):
    for item in range(5):
        if tool_download_file(
            url=url,
            location=location,
            filename=tool_remove_emoji(filename, "_", allow_emoji=True)
        ):
            break
    else:
        return False

    return True


def tool_write_meta(
        location: str,
        post_id: str,
        title: str,
        content_type: str,
        author_nickname: str,
        created_at: float,
):

    # create dir
    os.makedirs(location, exist_ok=True)

    # format
    meta_text = (
        f"""========VLIVE-BACKUP-BOT========

CONTENT-TYPE: {content_type}
TITLE: {title}
AUTHOR: {author_nickname}
TIME: {format_epoch(created_at, "%Y-%m-%d %H:%M:%S")}
ORIGIN: https://www.vlive.tv/post/{post_id}
BOT-SAVED: {vlivepy.parser.format_epoch(time.time(), "%Y-%m-%d %H:%M:%S")}

================================

""")
    current_date = "[%s]" % format_epoch(created_at, "%Y-%m-%d")
    # write
    with open(f"{location}/{current_date} {post_id}-info.txt", encoding="utf8", mode="w") as f:
        f.write(meta_text)


def shutdown():
    result = button_dialog(
        title='VLIVE-BACKUP-BOT',
        text='All tasks completed\nPress the Enter key to exit the program.',
        buttons=[
            ('End', True),
        ],
    ).run()
    if result:
        # clear()
        print("VLIVE-BACKUP-BOT by @box_archived")
        print()
        exit()


def dialog_error_message(text):
    message_dialog(
        title="Error",
        text=text,
    ).run()


def dialog_yn(title, text):
    return button_dialog(
        title=title,
        text=text,
        buttons=[
            ('Yes', True),
            ('No', False),
        ],
    ).run()


def dialog_download_end():
    return dialog_yn("Download complete", "Download complete.\nWould you like to download additional bulletin boards?")


def query_update(result: tuple):
    if not result[0]:
        return False

    update = dialog_yn(
        title="Update notification",
        text="A new update has been found\nDo you want to download the update?\n\n[Caution] Do not end the program during the update."
    )

    update_success = False

    def callback_fn(report_progress, report_log):
        nonlocal result
        nonlocal update_success
        report_progress(0)
        report_log("Get the update file.\n")
        sr = reqWrapper.get(result[1])
        if sr.success:
            try:
                # Overwrite path
                if os.path.isdir("_update"):
                    from shutil import rmtree
                    rmtree("_update")
                os.makedirs("_update", exist_ok=True)

                # Write update zip
                with open("_update/data.zip", "wb") as f:
                    f.write(sr.response.content)

                report_progress(35)
                report_log("Check for update files.\n")
                # extract
                from zipfile import ZipFile
                with ZipFile("_update/data.zip") as f:
                    f.extractall("_update")

                # find
                from glob import glob
                files = glob("_update/*")
                target = ''
                for item in files:
                    if "data.zip" not in item:
                        target = item

                report_progress(50)
                report_log("Updating.\n")
                # write
                for item in glob(f"{target}/*.*"):
                    filename = item.replace("\\", "/").rsplit("/", 1)[-1]

                    with open(item, "rb") as fi:
                        with open(filename, "wb") as fo:
                            fo.write(fi.read())

                report_progress(90)
                report_log("Clean up received files.\n")
                # Clean up path
                if os.path.isdir("_update"):
                    from shutil import rmtree
                    rmtree("_update")

                    update_success = True
                report_progress(100)
            except:
                report_progress(100)
        report_progress(100)

    if update:
        progress_dialog("Update", "", callback_fn).run()
        if update_success:
            message_dialog("Update successful", "The update is complete.\nPlease rerun the program to apply.").run()
            exit()
            return True
        else:
            message_dialog("Update failed", "Update failed.\nPlease proceed with the update manually.").run()
            open_new_tab(result[2])
            return False

    return False


def query_license_agreement():
    lic = ""
    lic += 'This software is free software and is licensed under the GPL-3.0 License.\n'
    lic += "The full text of the license can be found in the Github repo\n\n"
    lic += "The user is responsible for the use of this software,\n"
    lic += "Sharing the saved video with others may violate the copyright law.."

    if not button_dialog(
            title='License',
            text=lic,
            buttons=[
                ('Agree', True),
                ('Disagree', False),
            ],
    ).run():
        shutdown()


def query_workflow_select():
    return button_dialog(
        title='Select Mode',
        text="Please select a download mode\n\nSimple Mode: Saves all posts on the board page.\nAdvanced Mode: Specify download options.",
        buttons=[
            ('Simple Mode', True),
            ('Advanced Mode', False),
        ],
    ).run()


def query_download_url():
    url_rule = re.compile(r'((?<=vlive.tv/channel/).+(?=/board/))/board/(\d+)')
    target_url = ""
    while True:
        target_url = input_dialog(
            title="Enter download URL",
            text="Enter the address of the bulletin board to download.\n(Yes: https://www.vlive.tv/channel/B039DF/board/6118 )",
            ok_text="Confirm",
            cancel_text="Paste",
        ).run()
        if target_url is None:
            try:
                target_url = pyclip.paste().decode()
            except:
                target_url = ""

        regex_result = url_rule.findall(target_url)
        if len(regex_result) == 1:
            if dialog_yn(
                    title='Confirm',
                    text='Is the information you entered correct?\n\nChannel: %s\nBoard: %s' % (regex_result[0][0], regex_result[0][1]),
            ):
                return regex_result[0]
        else:
            dialog_error_message("Invalid URL!")


def query_membership():
    membership_yn = dialog_yn(
        title='Membership selection',
        text='Is it membership (fanship) content?',
    )

    if membership_yn:
        # Session exist check
        if os.path.isfile("cache/vlive-backup-bot.session"):
            with open("cache/vlive-backup-bot.session", "rb") as f:
                loaded_email = vlivepy.loadSession(f).email
            if dialog_yn("login", "Login history exists.\nWould you like to use an existing session?\n\nAccount information: %s" % loaded_email):
                return True

        # Login
        while True:

            user_email = ""
            while len(user_email) == 0:
                user_email = input_dialog(
                    title="login",
                    text="Please enter your VLIVE email ID.",
                    ok_text="Confirm",
                    cancel_text="Cancel",
                ).run()
                if user_email is None:
                    if dialog_yn("login", "Are you sure you want to cancel your login?"):
                        return False
                    else:
                        user_email = ""
                        continue

            # password
            user_pwd = ""
            while len(user_pwd) == 0:
                user_pwd = input_dialog(
                    title="login",
                    text="Enter your VLIVE password.",
                    ok_text="Confirm",
                    cancel_text="Cancel",
                    password=True
                ).run()
                if user_pwd is None:
                    if dialog_yn("Login", "Are you sure you want to cancel your login?"):
                        return False
                    else:
                        user_pwd = ""
                        continue

            login_callback_result = False

            # try login
            def login_try(report_progress, report_log):
                nonlocal login_callback_result
                report_log("Trying to log in.\n")
                report_progress(50)
                try:
                    sess = vlivepy.UserSession(user_email, user_pwd)
                except vlivepy.exception.APISignInFailedError:
                    # break
                    report_log("Login failed.\n")
                    login_callback_result = False
                    report_progress(100)
                else:
                    report_progress(75)
                    # dump session
                    report_log("Create a session file.\n")
                    with open("cache/vlive-backup-bot.session", "wb") as f_sess:
                        vlivepy.dumpSession(sess, f_sess)

                    # break
                    report_log("Login was successful.\n")
                    time.sleep(1)
                    login_callback_result = True
                    report_progress(100)

            progress_dialog("Login", None, login_try).run()
            if login_callback_result:
                return True
            else:
                dialog_error_message("Login failed.\nPlease check your account information.")

    return membership_yn


def query_options():
    opt_ovp = dialog_yn("Option", "Would you like to download the official video?")
    opt_post = dialog_yn("Option", "Do you want to download the post?")
    opt_amount = None
    while opt_amount is None:
        opt_amount = input_dialog(
            title="Option",
            text="Please enter the number of downloads.\nPosts will be determined in the latest order.\n\n(Enter 0 for all downloads)",
            ok_text="Confirm",
            cancel_text="Reset",
        ).run()
        try:
            opt_amount = int(opt_amount)
        except ValueError:
            dialog_error_message("Invalid value.")
            opt_amount = None
            continue
        except TypeError:
            opt_amount = None
            continue
        else:
            return opt_ovp, opt_post, opt_amount


def query_realname():
    return dialog_yn("Option", "Would you like to use the title of the original Vlive as the saved file name?\n"
                           "If you select No, only the post number is saved.\n\n (If saving as a title is not possible, it is saved as post number)")


def proc_load_post_list(target_channel, target_board, target_amount, membership):
    post_list = deque()

    def callback_fn(report_progress, report_log):
        report_progress(0)
        nonlocal post_list
        kwargs = {}
        # Add latest option when amount specified
        if target_amount != 0:
            kwargs.update({"latest": True})

        # Add session when membership
        if membership:
            with open("cache/vlive-backup-bot.session", "rb") as f:
                kwargs.update({"session": vlivepy.loadSession(f)})

        it = vlivepy.board.getBoardPostsIter(target_channel, target_board, **kwargs)
        cnt = 0
        page = 1
        try:
            for item in it:
                if cnt == 0:
                    report_log("%03d Load the page\n" % page)
                    page += 1

                cnt += 1

                post_list.append(item)

                if cnt == 20:
                    cnt = 0
                if len(post_list) == target_amount:
                    break

            report_progress(100)
        except vlivepy.exception.APIServerResponseError:
            post_list = None
            report_progress(100)

    progress_dialog(
        title="Loading posts...",
        text="Load a list of posts.\n This will take some time.",
        run_callback=callback_fn
    ).run()

    return post_list


def query_use_cache(channel_id, board_id, post_list: deque):
    cache_file_name = f"cache/{channel_id}_{board_id}.txt"
    if os.path.isfile(cache_file_name):
        opt_cache = dialog_yn("Option", "There is a history of downloading the bulletin board.\nDo you want to exclude previously received files?")
        if opt_cache:
            with open(cache_file_name, "r") as f:
                cached_list = f.read().splitlines()
            new_list = deque()
            while post_list:
                item: vlivepy.board.BoardPostItem = post_list.popleft()
                if item.post_id not in cached_list:
                    new_list.append(item)
            return new_list
    return post_list


def query_post_select(post_list: deque, opt_ovp, opt_post):
    def item_parser(post_item: vlivepy.board.BoardPostItem):
        description = "[%s] %s" % (
            format_epoch(post_item.created_at, "%Y-%m-%d"),
            tool_clip_text_length(tool_remove_emoji(post_item.title, "?"), 50)
        )
        return post_item, description

    filtered_list = list()
    check_dialog = None
    check_result = None

    def parser_progress(report_progress, report_log):
        nonlocal filtered_list
        nonlocal post_list
        nonlocal check_dialog
        initial_len = len(post_list)
        cnt = 0

        report_log("Reading the list...\n")
        while post_list:
            item: vlivepy.board.BoardPostItem = post_list.popleft()
            item_ovp = item.has_official_video
            if item_ovp and opt_ovp:
                filtered_list.append(item_parser(item))
            elif not item_ovp and opt_post:
                filtered_list.append(item_parser(item))

            cnt += 1
            report_progress(tool_calc_percent(initial_len, cnt))
            if len(filtered_list) == 0:
                report_progress(100)

        report_log("Prepare a list.")
        check_dialog = checkboxlist_dialog(
            title="Choose a post",
            text="Choose a post to download.",
            values=filtered_list,
            ok_text="Confirm",
            cancel_text="Select All"
        )
        report_progress(100)

    progress_dialog("Choose a post", None, parser_progress).run()

    if check_dialog is not None:
        check_result = check_dialog.run()
    if check_result is None:
        check_result = map(lambda x: x[0], filtered_list)

    return deque(check_result)


def proc_downloader(download_queue, channel_id, board_id, opt_realname):
    def callback_fn(report_progress, report_log):
        def report_fail(post_id):
            report_log("Failure")
            with open("failed.txt", encoding="utf8", mode="a") as f_report:
                f_report.write(f"https://www.vlive.tv/post/{post_id}\n")
        # set base dir
        channel_board_pair = f"{channel_id}_{board_id}"
        base_dir = f"downloaded/{channel_board_pair}"

        # set count of queue
        initial_length = len(download_queue)

        # download proc
        while download_queue:

            # report
            current_percent = tool_calc_percent(initial_length, initial_length - len(download_queue))
            report_progress(current_percent)
            current_target = download_queue.popleft()
            current_target: vlivepy.board.BoardPostItem
            log_format = "\n(%4.01f%%%%)(%s) [%s] Proceed to download......." % (
                current_percent, tool_format_creator(initial_length), current_target.post_id
            )
            report_log(log_format % (initial_length - len(download_queue), initial_length))

            current_date = "[%s]" % format_epoch(current_target.created_at, "%Y-%m-%d")

            current_location = "%s/%s %s" % (
                base_dir, current_date, current_target.post_id
            )

            if current_target.has_official_video:
                # type OfficialVideoPost

                try:
                    ovp = current_target.to_object()
                except:
                    report_fail(current_target.post_id)
                    continue

                # Pass when live
                if ovp.official_video_type != "VOD":
                    report_fail(current_target.post_id)
                    continue

                try:
                    ovv = ovp.official_video()
                except:
                    report_fail(current_target.post_id)
                    continue

                if ovv.vod_secure_status == "COMPLETE":
                    report_fail(current_target.post_id)
                    continue

                # Find max res source
                try:
                    max_source = vlivepy.parser.max_res_from_play_info(ovv.getVodPlayInfo())['source']
                except KeyError:
                    report_fail(current_target.post_id)
                    continue
                else:
                    if opt_realname:
                        ovp_filename = f"{current_date} {current_target.title}"
                    else:
                        ovp_filename = f"{current_date} {current_target.post_id}-video"
                    # download
                    if not proc_redundant_download(
                        url=max_source,
                        location=current_location,
                        filename=f"{ovp_filename}"
                    ):
                        report_fail(current_target.post_id)
                        continue
                    else:
                        report_log("Success")
            else:
                # type Post
                post = current_target.to_object()

                html = post.formatted_body()

                soup = BeautifulSoup(html, 'html.parser')
                imgs = soup.find_all("img")
                img_cnt = 0

                # download image
                for item in imgs:
                    img_cnt += 1

                    item: element
                    dnld_image_name = "%s %s-img-%02d" % (current_date, current_target.post_id, img_cnt)
                    if not proc_redundant_download(
                        url=item['src'],
                        location=current_location,
                        filename=dnld_image_name
                    ):
                        report_fail(current_target.post_id)
                        continue
                    item['src'] = f"{dnld_image_name}.{tool_parse_url(item['src'])[0]}"

                # download video
                videos = soup.find_all("video")
                video_cnt = 0
                for item in videos:
                    item: element
                    video_cnt += 1

                    # Poster get
                    dnld_poster_name = "%s %s-poster-%02d" % (current_date, current_target.post_id, video_cnt)
                    if not proc_redundant_download(
                        url=item['poster'],
                        location=current_location,
                        filename=dnld_poster_name
                    ):
                        report_fail(current_target.post_id)
                        continue
                    item['poster'] = f"{dnld_poster_name}.{tool_parse_url(item['poster'])[0]}"

                    # Video get
                    dnld_video_name = "%s %s-video-%02d" % (current_date, current_target.post_id, video_cnt)
                    if not proc_redundant_download(
                        url=item['src'],
                        location=current_location,
                        filename=dnld_video_name
                    ):
                        report_fail(current_target.post_id)
                        continue
                    item['src'] = f"{dnld_video_name}.{tool_parse_url(item['src'])[0]}"

                # Get star-comment
                comment_html = """\n<div style="padding-top:5px"><h3>스타 댓글</h3></div>"""

                for comment_item in post.getPostStarCommentsIter():
                    comment_html += '<div style="padding-top:5px;width:720px;border-top:1px solid #f2f2f2;border-bottom:1px solid #f2f2f2">'
                    comment_html += '<div style="margin: 15px 0 0 15px">'
                    comment_html += f'<span style="font-weight:700; font-size:13px; margin-right:10px">{comment_item.author_nickname}</span>'
                    comment_html += f'<span style="font-size:12px; color:#777;">{format_epoch(comment_item.created_at, "%Y-%m-%d %H:%M:%S")}</span>'
                    comment_html += '</div>'
                    comment_html += f'<div style="margin: 0 0 15px 15px; font-size:14px">{comment_item.body}</div>'
                    comment_html += '</div>'

                os.makedirs(current_location, exist_ok=True)
                post_filename = f"{current_location}/{current_date} {current_target.post_id}-post.html"
                if opt_realname:
                    filename_safe_title = tool_regex_window_name(tool_remove_emoji(current_target.title, "_", True))
                    max_len_name = tool_max_len_filename(
                        current_location,
                        f"{current_date} {filename_safe_title}",
                        "html"
                    )
                    post_real_name = f"{current_location}/{max_len_name}.html"
                    try:
                        open(post_real_name, "w").close()
                    except OSError:
                        pass
                    else:
                        post_filename = post_real_name

                with open(post_filename, encoding="utf8", mode="w") as f:
                    f.write(str(soup))
                    f.write(comment_html)

                report_log("Success")

            # Write meta
            tool_write_meta(
                location=current_location,
                post_id=current_target.post_id,
                title=current_target.title,
                content_type=current_target.content_type,
                author_nickname=current_target.author_nickname,
                created_at=current_target.created_at,
            )
            with open(f"cache/{channel_board_pair}.txt", encoding="utf8", mode="a") as f:
                f.write(f"{current_target.post_id}\n")
            time.sleep(0.2)

        # Download End
        report_progress(100)

    progress_dialog(
        title="VLIVE Download",
        text="VLIVE bulletin board backup is in progress.\nThis will take some time.",
        run_callback=callback_fn
    ).run()


def main():
    os.makedirs("downloaded", exist_ok=True)
    os.makedirs("cache", exist_ok=True)
    clear()
    easy_mode = query_workflow_select()

    target_channel, target_board = query_download_url()

    membership = query_membership()

    # Select option on adv-mode
    if easy_mode:
        opt_ovp = True
        opt_post = True
        opt_amount = 0

    else:
        opt_ovp, opt_post, opt_amount = query_options()

        if not opt_ovp and not opt_post:
            return dialog_download_end()

    post_list = proc_load_post_list(
        target_channel=target_channel,
        target_board=target_board,
        target_amount=opt_amount,
        membership=membership,
    )
    if post_list is None:
        dialog_error_message("You do not have permission to load this board.")
        return dialog_download_end()

    post_list = query_use_cache(target_channel, target_board, post_list)

    # Post select dialog on adv-mode
    if not easy_mode:
        post_list = query_post_select(post_list, opt_ovp, opt_post)

    opt_realname = query_realname()

    # Downloader Query
    proc_downloader(post_list, target_channel, target_board, opt_realname)

    return dialog_download_end()


if __name__ == '__main__':
    query_update(dialog_splash())

    query_license_agreement()

    while True:
        if main():
            continue
        else:
            shutdown()
