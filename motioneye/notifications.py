
# Copyright (c) 2013 Fabijan Spralja
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import logging
import tasks

import settings



def queue_motion(camera_id, camera_config):
    try:
        import sendmail
        import socket
        import tzctl
        message = sendmail.messages['motion_start']
        format_dict = {
            'camera': camera_config['camera_name'],
            'hostname': socket.gethostname(),
            'moment': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        if settings.LOCAL_TIME_FILE:
            format_dict['timezone'] = tzctl.get_time_zone()

        else:
            format_dict['timezone'] = 'local time'

        message = message % format_dict

        # TODO motion email notification rework
        #if camera_config['@animation_email_enabled']:
        #    tasks.add(0, send_email_notification, tag='queue_animation(%s)' % anim_path,
        #              camera_config=camera_config, files=[anim_path])

        # motion telegram notification
        if camera_config['@telegram_enabled'] and camera_config['@telegram_motion_enabled']:

            tasks.add(0, send_telegram_notification, tag='queue_animation(%s)' % camera_id,
                      camera_config=camera_config, message=message)
            #send_telegram_notification(camera_config=camera_config, message=message)

    except Exception as e:
        logging.error('queue motion notification failed: %s' % e.message, exc_info=True)


def queue_animation(camera_config, anim_path):
    try:
        # TODO for some reason tasks queued from inside a task don't execute...

        # animation email notification
        if camera_config['@animation_email_enabled']:
            #tasks.add(0, send_email_notification, tag='queue_animation(%s)' % anim_path,
            #          camera_config=camera_config, files=[anim_path])
            send_email_notification(camera_config=camera_config, files=[anim_path])

        # animation telegram notification
        if camera_config['@telegram_enabled'] and camera_config['@telegram_animation_enabled']:
            #tasks.add(0, send_telegram_notification, tag='queue_animation(%s)' % anim_path,
            #          camera_config=camera_config, file=anim_path)
            send_telegram_notification(camera_config=camera_config, file=anim_path)

    except Exception as e:
        logging.error('queue animation notification failed: %s' % e.message, exc_info=True)


def send_email_notification(camera_config, files):
    import socket
    import sendmail
    import tzctl
    import smtplib

    logging.debug('sending animation email')

    try:
        subject = sendmail.subjects['motion_end']
        message = sendmail.messages['motion_start']
        format_dict = {
            'camera': camera_config['camera_name'],
            'hostname': socket.gethostname(),
            'moment': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        if settings.LOCAL_TIME_FILE:
            format_dict['timezone'] = tzctl.get_time_zone()

        else:
            format_dict['timezone'] = 'local time'

        message = message % format_dict
        subject = subject % format_dict

        sendmail.send_mail(camera_config['@animation_email_notifications_smtp_server'], int(camera_config['@animation_email_notifications_smtp_port']),
                           camera_config['@animation_email_notifications_smtp_account'], camera_config['@animation_email_notifications_smtp_password'],
                           camera_config['@animation_email_notifications_smtp_tls'], camera_config['@animation_email_notifications_from'],
                           [camera_config['@animation_email_notifications_addresses']],
                           subject=subject, message=message, files=files)

        logging.debug('animation email succeeded')

    except Exception as e:
        if isinstance(e, smtplib.SMTPResponseException):
            msg = e.smtp_error
        else:
            msg = str(e)
        logging.error('animation email failed: %s' % msg, exc_info=True)


def send_telegram_notification(camera_config, file=None, message=None):
    try:
        logging.debug('sending telegram notification')

        import telegram
        bot = telegram.Bot(token=camera_config['@telegram_token'])

        channel_name = camera_config.get('@telegram_name', 'bot')
        chat_cache_id = '%s_%s' % (camera_config['@telegram_token'], channel_name)
        chat_id = '@telegram_chat_id_%s' % chat_cache_id
        if camera_config.get(chat_id, None) is None:
            logging.debug("telegram me: %s" % bot.get_me())
            updates = bot.get_updates(allowed_updates=["message"], limit=5)
            for u in updates:
                logging.debug('finding chat_id in update message chat id: %s, type: %s, title: %s ' % (u.message.chat.id, u.message.chat.type, u.message.chat.title))
                import config
                if u.message.chat.type == 'private' and (channel_name == 'bot' or channel_name == ''):
                    logging.debug('found telegram chat_id %s for bot: %s' % (u.message.chat.id, channel_name))

                    if camera_config["@id"] is not None:
                        camera_config[chat_id] = u.message.chat.id
                        config.set_camera(camera_config['@id'], camera_config)

                    break
                elif u.message.chat.type != 'private' and channel_name == u.message.chat.title:
                    logging.debug("found telegram chat_id %s for group: %s" % (u.message.chat.id, channel_name))

                    if camera_config["@id"] is not None:
                        camera_config[chat_id] = u.message.chat.id
                        config.set_camera(camera_config['@id'], camera_config)

                    break

        if camera_config.get(chat_id, None) is None:
            logging.error('no chat_id found for telegram token and telegram_name %s, try sending a message to group or bot...' % channel_name)
            return 'no chat_id found for telegram token and telegram_name %s, try sending a message to the group/bot...' % channel_name

        if file is not None:
            logging.debug('sending photo to telegram %s chat_id: %s' % (channel_name, camera_config[chat_id]))
            bot.send_animation(chat_id=camera_config[chat_id], animation=open(file, 'rb'), caption=message)
        else:
            logging.debug(
                'sending text to telegram %s chat_id: %s' % (channel_name, camera_config[chat_id]))
            bot.send_message(chat_id=camera_config[chat_id], text=message)
        return None

    except Exception as e:
        logging.error('queue animation notification telegram failed: %s' % e.message, exc_info=True)
        return e.message


#def config_changed():
    #logging.debug('clearing telegram chat_id cache...')
    #global _telegram_chat_ids
    #_telegram_chat_ids = {}