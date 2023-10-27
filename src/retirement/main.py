# -*- coding: utf-8 -*-
#

import json
import copy
import time
from os.path import join, dirname, basename
from pathlib import Path

import aqt
from aqt import mw, gui_hooks
from aqt.deckoptions import DeckOptionsDialog
from aqt.qt import (QAction, QGroupBox, QHBoxLayout, QIcon, QLineEdit, QMenu,
                    QPushButton, QRadioButton, QProgressBar, QDialog, QLabel,
                    QVBoxLayout, QWidget, Qt)
from aqt.utils import tooltip, showInfo

import anki.find
from anki.hooks import wrap
from anki.utils import ids2str, int_time, is_mac
from anki.scheduler import v3
# from anki.collection import _Collection, LegacyReviewUndo, LegacyCheckpoint


addon_path = dirname(__file__)

verNumber = "23.10"


def get_config():
    return mw.addonManager.getConfig(__name__)


RetirementTag = get_config()["Retirement Tag"]


def attempt_starting_refresh():
    starting_refresh()


def starting_refresh():
    refresh_config()
    if mw.RetroactiveRetiring:
        apply_retirement_actions()
    elif mw.DailyRetiring:
        if time.time() - mw.LastMassRetirement > 86400000:
            apply_retirement_actions()


def refresh_config():
    global RetirementDeckName, RetirementTag, RealNotifications, RetroNotifications
    config = get_config()
    RetirementDeckName = config["Retirement Deck Name"]
    RetirementTag = config["Retirement Tag"]
    mw.RetroactiveRetiring = False
    RealNotifications = False
    RetroNotifications = False
    mw.DailyRetiring = False
    mw.LastMassRetirement = config["Last Mass Retirement"]
    if config["Mass Retirement on Startup"] == 'on':
        mw.RetroactiveRetiring = True
    if config["Mass Retirement on Startup"] == 'once':
        mw.DailyRetiring = True
    if config["Real-time Notifications"] == 'on':
        RealNotifications = True
    if config["Mass Retirement Notifications"] == 'on':
        RetroNotifications = True


def cb_status_check(dn, sc, tn, mc):
    if dn.isChecked():
        sc.setEnabled(False)
        tn.setEnabled(False)
        mc.setEnabled(False)
    else:
        sc.setEnabled(True)
        tn.setEnabled(True)
        mc.setEnabled(True)

def add_retirement_opts(dialog: DeckOptionsDialog) -> None:
    file = Path(__file__)
    with open(file.with_name("options.html"), encoding="utf8") as f:
        html = f.read()
    with open(file.with_name("options.js"), encoding="utf8") as f:
        script = f.read()

    dialog.web.eval(script.replace("HTML_CONTENT", json.dumps(html)))


def add_retirement_opts(self, Dialog):
    row = self.gridLayout_3.rowCount()
    wid = QLabel("<b>Card Retirement</b>")
    self.gridLayout_3.addWidget(wid, row, 0, 1, 1)
    row += 1
    self.rInt = QSpinBox()
    self.rInt.setValue(0)
    self.rInt.setMinimum(0)
    self.rInt.setMaximum(99999)
    self.easyBonus.setFixedWidth(60)
    self.revPerDay.setFixedWidth(60)
    self.maxIvl.setFixedWidth(60)
    self.fi1.setFixedWidth(60)
    self.hardFactor.setFixedWidth(60)
    self.rInt.setFixedWidth(60)

    self.label_23.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
    self.gridLayout_3.addWidget(
            QLabel("Retiring interval (0 = off)"), row, 0, 1, 1)
    self.gridLayout_3.addWidget(self.rInt, row, 1, 1, 1)
    day_lab = QLabel("days")
    day_lab.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
    self.gridLayout_3.addWidget(day_lab, row, 2, 1, 1)
    row += 1
    wid = QLabel("Retirement actions")
    self.gridLayout_3.addWidget(wid, row, 0, 1, 1)

    self.dn = QCheckBox("Delete")
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setStyleSheet("color: grey;")
    self.sc = QCheckBox("Suspend")
    self.tn = QCheckBox("Tag")
    self.mc = QCheckBox("Move")
    self.dn.setToolTip(
            "WARNING: Applies on a per-note basis; all related cards will be deleted.")
    self.sc.setToolTip("Applies on a per-card basis.")
    self.tn.setToolTip(
            "Applies on a per-note basis; all related cards will be tagged.")
    self.mc.setToolTip("Applies on a per-card basis.")
    self.dn.clicked.connect(lambda: cb_status_check(
            self.dn, self.sc, self.tn, self.mc))
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    layout.addWidget(self.dn)
    layout.addWidget(sep)
    layout.addWidget(QLabel("<span>&nbsp;</span>"))
    layout.addWidget(self.sc)
    layout.addWidget(self.tn)
    layout.addWidget(self.mc)
    layout.addStretch()
    self.gridLayout_3.addLayout(layout, row, 1, 1, 2)


def save_retirement(self):
    c = self.conf['new']
    f = self.form
    c['retiringInterval'] = f.rInt.value()
    c['retirementActions'] = {'delete': f.dn.isChecked(), 'suspend': f.sc.isChecked(
    ), 'tag': f.tn.isChecked(), 'move': f.mc.isChecked()}


def load_retirement(self):

    c = self.conf['new']
    f = self.form
    if 'retiringInterval' not in c:
        c['retiringInterval'] = 0
    if 'retirementActions' not in c:
        c['retirementActions'] = {'delete': False,
                                  'suspend': True, 'tag': True, 'move': False}
    f.rInt.setValue(c['retiringInterval'])
    f.dn.setChecked(c['retirementActions']['delete'])
    f.sc.setChecked(c['retirementActions']['suspend'])
    f.tn.setChecked(c['retirementActions']['tag'])
    f.mc.setChecked(c['retirementActions']['move'])
    if f.dn.isChecked():
        f.sc.setEnabled(False)
        f.tn.setEnabled(False)
        f.mc.setEnabled(False)


def ra_set(ra):
    for a in ra:
        if ra[a]:
            return True
    return False


def get_progress_widget():
    progress_widget = QWidget(None)
    layout = QVBoxLayout()
    progress_widget.setFixedSize(400, 70)
    progress_widget.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress_widget.setWindowIcon(QIcon(join(addon_path, 'icon.png')))
    progress_widget.setWindowTitle("Running Mass Retirement...")
    progress_bar = QProgressBar(progress_widget)
    if is_mac:
        progress_bar.setFixedSize(380, 50)
    else:
        progress_bar.setFixedSize(390, 50)
    progress_bar.move(10, 10)
    per = QLabel(progress_bar)
    per.setAlignment(Qt.AlignmentFlag.AlignCenter)
    progress_widget.show()
    return progress_widget, progress_bar


def apply_retirement_actions(notes=False, show_notification=True, optimizer=False):
    time_start = time.time()
    notes_to_delete = []
    cards_to_move = []
    suspended = 0
    tagged = 0
    total = 0
    progress_widget, progress_bar = get_progress_widget()
    if not optimizer:
        mw.checkpoint('Card Retirement')
    if not notes:
        notes = grab_col()
    checkpointed = True
    progress_bar.setMinimum(0)
    progress_bar.setMaximum(len(notes))
    count = 0
    for nid in notes:
        count += 1
        if count % 10 == 0:
            progress_bar.setValue(count)
            mw.app.processEvents()
        note = mw.col.get_note(nid)
        cards = note.cards()

        for card in cards:
            if card.ivl == 0:
                continue
            notes_to_delete, cards_to_move, suspended, tagged, total, checkpointed = handle_retirement_actions(
                    card, note, notes_to_delete, cards_to_move, suspended, tagged, total, checkpointed)
    notification = ''
    ndl = len(notes_to_delete)
    cml = len(cards_to_move)
    progress_widget.hide()
    if suspended > 0:
        notification += '- ' + str(suspended) + ' card(s) have been suspended<br>'
    if tagged > 0:
        notification += '- ' + str(tagged) + ' note(s) have been tagged<br>'
    if cml > 0:
        notification += '- ' + str(cml) + ' card(s) have been moved<br>'
        move_to_deck(cards_to_move)
    if ndl > 0:
        notification += '- ' + str(ndl) + ' note(s) have been deleted<br>'
        mw.col.remove_notes(notes_to_delete)
    time_end = time.time()
    if notification != '' and RetroNotifications:
        display_notification('<b>' + str(total) + ' card(s) have been retired in ' + str(
                round(time_end - time_start, 3)) + ' seconds:</b><br>' + notification)
    mw.reset()
    save_ass_retirement_timestamp(time.time())


def set_checkpointed(checkpointed, review):
    if not checkpointed and not review:
        mw.checkpoint("Card Retirement")
    return True


def handle_retirement_actions(
                card,
                note,
                notes_to_delete,
                cards_to_move,
                suspended,
                tagged,
                total,
                checkpointed,
                review=False):
    deck_config = mw.col.decks.config_dict_for_deck_id(card.odid or card.did)
    if 'retirementOptions' in deck_config:
        config = deck_config['retirementOptions']
        if config['retire']:
            retire_interval = config['retireInterval']
            if card.ivl > retire_interval:
                total += 1
                if config['delete']:
                    checkpointed = set_checkpointed(checkpointed, review)
                    if note.id not in notes_to_delete:
                        notes_to_delete.append(note.id)
                else:
                    if config['suspend']:
                        checkpointed = set_checkpointed(checkpointed, review)
                        if card.queue != -1:
                            suspended += 1
                            card.queue = -1
                            mw.col.update_card(card)

                    if config['tag']:
                        checkpointed = set_checkpointed(checkpointed, review)
                        if not note.has_tag(RetirementTag):
                            tagged += 1
                            note.add_tag(RetirementTag)
                            mw.col.update_note(note)
                    if config['move']:
                        checkpointed = set_checkpointed(checkpointed, review)
                        if card.did != mw.col.decks.id(RetirementDeckName):
                            cards_to_move.append(card.id)
    return notes_to_delete, cards_to_move, suspended, tagged, total, checkpointed


def display_notification(text):
    showInfo(text=text, help="", type="info", title="Card Retirement")


def grab_col():
    return mw.col.find_notes("")


def move_to_deck(cids, ogDeckId=False):
    if ogDeckId:
        did = ogDeckId
    else:
        did = mw.col.decks.id(RetirementDeckName)
    from aqt.studydeck import StudyDeck
    if not cids:
        return
    deck = mw.col.decks.get(did)
    if deck['dyn']:
        return
    mod = int_time()
    usn = mw.col.usn()
    scids = ids2str(cids)
    mw.col.sched.remFromDyn(cids)
    mw.col.db.execute("""update cards set usn=?, mod=?, did=? where id in """ + scids, usn, mod, did)


def check_interval(self, card, ease):
    working_card = copy.copy(card)
    notes_to_delete = []
    cards_to_move = []
    suspended = 0
    tagged = 0
    total = 0
    checkpointed = False
    note = mw.col.get_note(card.nid)
    notes_to_delete, cards_to_move, suspended, tagged, total, checkpointed = handle_retirement_actions(
            card, note, notes_to_delete, cards_to_move, suspended, tagged, total, checkpointed, True)
    ndl = len(notes_to_delete)
    cml = len(cards_to_move)
    if suspended > 0 or tagged > 0 or cml > 0 or ndl > 0:
        last = len(mw.col._undo.entries) - 1

        mw.col._undo.entries[last].retirementActions = []
        if cml > 0:
            mw.col._undo.entries[last].retirementActions.append('move')
            mw.col._undo.entries[last].retirementActions.append(card.did)
            move_to_deck(cards_to_move)
            mw.col.db.commit()
        if ndl > 0:
            undo_copy = mw.col._undo
            mw.checkpoint("Card Retirement")
            mw.col._undo.append(undo_copy)
            mw.col.remove_notes(notes_to_delete)
        if tagged > 0:
            mw.col._undo.entries[last].retirementActions.append('tag')
        if RealNotifications:
            tooltip('The card has been retired.')


# def retirementUndoReview(self):
#     last = len(mw.col._undo.entries) - 1

#     if (
#             isinstance(mw.col._undo.entries[last], LegacyReviewUndo)
#             and hasattr(mw.col._undo.entries[last], "retirementActions")
#             and len(mw.col._undo.entries[last].retirementActions) > 0
#     ):
#         data: LegacyReviewUndo = mw.col._undo.entries[last]
#         card = data.card
#         # if not data:
#         # self.clearUndo()
#         if not data.was_leech and card.note().hasTag("leech"):
#             card.note().delTag("leech")
#             card.note().flush()
#         if 'tag' in data.retirementActions:
#             card.note().delTag(RetirementTag)
#             card.note().flush()
#         if data.retirementActions[0] == 'move':
#             moveToDeck([card.id], data.retirementActions[1])
#         del data.retirementActions
#         card.flush()
#         last = self.db.scalar(
#                 "select id from revlog where cid = ? "
#                 "order by id desc limit 1", card.id)
#         self.db.execute("delete from revlog where id = ?", last)
#         self.db.execute(
#                 "update cards set queue=type,mod=?,usn=? where queue=-2 and nid=?",
#                 intTime(), self.usn(), card.nid)
#         n = 1 if card.queue == 3 else card.queue
#         type = ("new", "lrn", "rev")[n]
#         self.sched._updateStats(card, type, -1)
#         self.sched.reps -= 1
#         return LegacyReviewUndo(card, was_leech=data.was_leech)
#     else:
#         return ogUndoReview(mw.col)


# def retirementUndo(self):
#     last = len(mw.col._undo.entries) - 1
#     if (isinstance(mw.col._undo.entries[last], LegacyCheckpoint)
#                     and mw.col._undo.entries[last].action == "Card Retirement" and len(self._undo.entries) > 2):
#         tempUndo = self._undo.entries[last]
#         self.rollback()
#         self.clearUndo()
#         self._undo.entries.insert(0, tempUndo)
#         self.undo()
#     else:
#         return ogUndo(mw.col)


# ogUndoReview = _Collection._undo_review
# _Collection._undo_review = retirementUndoReview

# ogUndo = _Collection.undo
# _Collection.undo = retirementUndo


def save_config(wid, rdn, rt, retro_r, daily_r, real_n, retro_n):
    if retro_r:
        retro_r = 'on'
    elif daily_r:
        retro_r = 'once'
    else:
        retro_r = 'off'
    if real_n:
        real_n = 'on'
    else:
        real_n = 'off'
    if retro_n:
        retro_n = 'on'
    else:
        retro_n = 'off'
    conf = {
            "Retirement Deck Name": rdn,
            "Retirement Tag": rt,
            "Mass Retirement on Startup": retro_r,
            "Real-time Notifications": real_n,
            "Mass Retirement Notifications": retro_n,
            "Last Mass Retirement": mw.LastMassRetirement}
    mw.addonManager.writeConfig(__name__, conf)
    refresh_config()
    wid.hide()


def testretire():
    apply_retirement_actions()


def open_settings():
    retirement_menu = QDialog(mw)
    retirement_menu.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
    l1 = QLabel()
    l1.setText('Retirement Deck Name:')
    l1.setToolTip(
        "The name of the deck retired cards are sent to. Default: “Retired Cards”")
    l1.setFixedWidth(200)
    rdn = QLineEdit()
    rdn.setFixedWidth(229)
    l2 = QLabel()
    l2.setText('Retirement Tag:')
    l2.setToolTip("The tag added to retired cards. Default: “Retired”")
    l2.setFixedWidth(200)
    rt = QLineEdit()
    rt.setFixedWidth(229)
    l3 = QLabel()
    l3.setText('Run Mass Retirement:')
    l3.setToolTip("Automatically run mass retirement on profile load.")
    l3.setFixedWidth(210)
    bg1 = QGroupBox()
    bg1b1 = QRadioButton("On Startup")
    bg1b1.setFixedWidth(90)
    bg1b2 = QRadioButton("Once Daily")
    bg1b2.setFixedWidth(90)
    bg1b3 = QRadioButton("Off")
    bg1b3.setFixedWidth(40)
    l4 = QLabel()
    l4.setText('Real-time Notifications:')
    l4.setToolTip(
            "Display a notification when a card is retired while reviewing.")
    l4.setFixedWidth(210)
    bg2 = QGroupBox()
    bg2b1 = QRadioButton("On")
    bg2b1.setFixedWidth(90)
    bg2b2 = QRadioButton("Off")
    bg2b2.setFixedWidth(100)
    l5 = QLabel()
    l5.setText('Mass Retirement Notifications:')
    l5.setToolTip(
            "After mass retirement, display a notification detailing results.")
    l5.setFixedWidth(210)
    bg3 = QGroupBox()
    bg3b1 = QRadioButton("On",)
    bg3b1.setFixedWidth(90)
    bg3b2 = QRadioButton("Off")
    bg3b2.setFixedWidth(100)
    applyb = QPushButton('Apply')
    applyb.clicked.connect(
            lambda: save_config(
                    retirement_menu,
                    rdn.text(),
                    rt.text(),
                    bg1b1.isChecked(),
                    bg1b2.isChecked(),
                    bg2b1.isChecked(),
                    bg3b1.isChecked()))
    applyb.setFixedWidth(100)
    cancelb = QPushButton('Cancel')
    cancelb.clicked.connect(lambda: retirement_menu.hide())
    cancelb.setFixedWidth(100)
    vh1 = QHBoxLayout()
    vh2 = QHBoxLayout()
    vh3 = QHBoxLayout()
    vh4 = QHBoxLayout()
    vh5 = QHBoxLayout()
    vh6 = QHBoxLayout()
    vh1.addWidget(l1)
    vh1.addWidget(rdn)
    vh2.addWidget(l2)
    vh2.addWidget(rt)
    vh3.addWidget(l3)
    vh3.addWidget(bg1b1)
    vh3.addWidget(bg1b2)
    vh3.addWidget(bg1b3)
    vh4.addWidget(l4)
    vh4.addWidget(bg2b1)
    vh4.addWidget(bg2b2)
    vh5.addWidget(l5)
    vh5.addWidget(bg3b1)
    vh5.addWidget(bg3b2)
    vh6.addStretch()
    vh6.addWidget(applyb)
    vh6.addWidget(cancelb)
    vh1.addStretch()
    vh2.addStretch()
    vh3.addStretch()
    vh4.addStretch()
    vh5.addStretch()
    vh6.addStretch()
    vl = QVBoxLayout()
    bg1.setLayout(vh3)
    bg2.setLayout(vh4)
    bg3.setLayout(vh5)
    vl.addLayout(vh1)
    vl.addLayout(vh2)
    vl.addWidget(bg1)
    vl.addWidget(bg2)
    vl.addWidget(bg3)
    vl.addLayout(vh6)
    load_current(rt, rdn, bg1b1, bg1b2, bg1b3, bg2b1, bg2b2, bg3b1, bg3b2)
    retirement_menu.setWindowTitle(
            "Retirement Add-on Settings (Ver. " + verNumber + ")")
    retirement_menu.setWindowIcon(QIcon(join(addon_path, 'icon.png')))
    retirement_menu.setLayout(vl)
    retirement_menu.show()
    retirement_menu.setFixedSize(retirement_menu.size())


def load_current(rt, rdn, bg1b1, bg1b2, bg1b3, bg2b1, bg2b2, bg3b1, bg3b2):
    rt.setText(RetirementTag)
    rdn.setText(RetirementDeckName)
    if mw.RetroactiveRetiring:
        bg1b1.setChecked(True)
    elif mw.DailyRetiring:
        bg1b2.setChecked(True)
    else:
        bg1b3.setChecked(True)
    if RealNotifications:
        bg2b1.setChecked(True)
    else:
        bg2b2.setChecked(True)
    if RetroNotifications:
        bg3b1.setChecked(True)
    else:
        bg3b2.setChecked(True)


def save_ass_retirement_timestamp(timestamp):
    config = get_config()
    config["Last Mass Retirement"] = timestamp
    mw.addonManager.writeConfig(__name__, config)


def setup_menu():
    sub_menu = QMenu('Retirement', mw)
    mw.form.menuTools.addMenu(sub_menu)

    retirement_settings = QAction("Retirement Settings", mw)
    retirement_settings.triggered.connect(open_settings)
    sub_menu.addAction(retirement_settings)

    mass_retirement = QAction("Run Mass Retirement", mw)
    mass_retirement.triggered.connect(testretire)
    sub_menu.addAction(mass_retirement)


setup_menu()
v3.Scheduler.answerCard = wrap(v3.Scheduler.answerCard, check_interval)
aqt.deckconf.DeckConf.loadConf = wrap(aqt.deckconf.DeckConf.loadConf, load_retirement)
aqt.deckconf.DeckConf.saveConf = wrap(aqt.deckconf.DeckConf.saveConf, save_retirement, "before")
aqt.forms.dconf.Ui_Dialog.setupUi = wrap(aqt.forms.dconf.Ui_Dialog.setupUi, add_retirement_opts)
gui_hooks.profile_did_open.append(attempt_starting_refresh)
gui_hooks.deck_options_did_load.append(add_retirement_opts)


def support_accept(self):
    if self.addon == basename(addon_path):
        refresh_config()


aqt.addons.ConfigEditor.accept = wrap(aqt.addons.ConfigEditor.accept, support_accept)


mw.refreshRetirementConfig = refresh_config
mw.runRetirement = apply_retirement_actions
