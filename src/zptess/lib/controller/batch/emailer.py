# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------
# Copyright (c) 2021
#
# See the LICENSE file for details
# see the AUTHORS file for authors
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

import logging
import os.path
import ssl
import smtplib
import email

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# -------------
# Local imports
# -------------

from zptool.utils import paging, read_property, section_read, section_display, update_property


# -----------------------
# Module global variables
# -----------------------

log = logging.getLogger("zptool")

# -----------------
# Utility functions
# -----------------

# Adapted From https://realpython.com/python-send-email/
def email_send(subject, body, sender, receivers, attachment, host, port, password, confidential=False):
    msg_receivers = receivers
    receivers = receivers.split(sep=',')
    message = MIMEMultipart()
    message["Subject"] = subject
    # Create a multipart message and set headers
    if confidential:
        message["From"] = sender
        message["To"]   = sender
        message["Bcc"]  = msg_receivers
    else:
        message["From"] = sender
        message["To"]   = msg_receivers

    # Add body to email
    message.attach(MIMEText(body, "plain"))

    # Open file in binary mode
    with open(attachment, "rb") as fd:
        # Add file as application/octet-stream
        # Email client can usually download this automatically as attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(fd.read())

    # Encode file in ASCII characters to send by email    
    encoders.encode_base64(part)

    # Add header as key/value pair to attachment part
    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {os.path.basename(attachment)}",
    )
    # Add attachment to message and convert message to string
    message.attach(part)
    # Log in to server using secure context and send email
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.ehlo()  # Can be omitted
        server.starttls(context=context)
        server.ehlo()  # Can be omitted
        server.login(sender, password)
        server.sendmail(sender, receivers, message.as_string())


# ================
# 'email' commands
# ================

def update(connection, options):
    '''Updates reference section in config database'''
    if options.host is not None:
        update_property(connection,'smtp','host',options.host)
    if options.port is not None:
        update_property(connection,'smtp','port',options.port)
    if options.sender is not None:
        update_property(connection,'smtp','sender',options.sender)
    if options.password is not None:
        update_property(connection,'smtp','password',options.password)
    if options.receivers is not None:
        receivers = ", ".join(options.receivers)
        update_property(connection,'smtp','receivers',receivers)
    view(connection, options)


def view(connection, options):
    '''View reference section in config database'''
    cursor = section_read(connection, 'smtp')
    attributes = cursor.fetchall()
    result = tuple(map(lambda t: tuple([t[0],t[1],'********']) if t[1] == 'password' else t, attributes))
    section_display(result)