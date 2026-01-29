# AutoSave Manager

A simple tool that automatically backs up your game saves at regular intervals. No more losing hours of progress because you forgot to save or the game crashed or the save got overwritten by a corrupted save.

## What It Does

- Creates zip backups of any folder you point it at
- Runs in the background while you play
- Keeps backups organized with timestamps
- Automatically deletes old backups so your disk doesn't fill up
- Lets you set up different profiles for different games

## Installation

Grab the latest `autosave_manager.exe` from the Releases page and put it wherever you want. That's it.

The app creates a `profiles.json` file next to the exe when you first run it. This is where your profiles and settings are stored. Keep these two files together - if you move the exe somewhere else, bring the json file with it or you'll lose your settings.

## How to Use

1. Run the exe

2. Create a new profile by clicking "New Profile" and giving it a name (like "Elden Ring" or "Baldur's Gate 3")

3. Set your paths:
   - **Source Folder**: Where your game saves its files. You'll need to look this up for your specific game, but it's usually somewhere in `%APPDATA%`, `%LOCALAPPDATA%`, or `Documents\My Games`
   - **Backup Folder**: Where you want the zip files to go. Pick somewhere with enough space.

4. Adjust the backup interval if you want (default is every 60 seconds)

5. Hit the big green "START BACKUP SERVICE" button

6. Leave the window open while you play. It'll keep backing up in the background.

All your settings are saved automatically as you change them.

## Settings

- **Backup Interval**: How often to create a backup, in seconds. 60 seconds is a good default, but you might want longer for games that save less frequently.
- **Max Backups to Keep**: The tool will automatically delete older backups once you have more than this number. Default is 100.

## Common Game Save Locations

Here are some places games commonly store saves. Your mileage may vary.

- Steam Cloud saves: `C:\Program Files (x86)\Steam\userdata\<your-id>\<game-id>\`
- Most modern games: `%LOCALAPPDATA%\<GameName>\Saved\`
- Older games: `Documents\My Games\<GameName>\`
- Some games: `%APPDATA%\<GameName>\`

If you can't find your saves, try searching the internet for the game name + "save location" or "save file location".

## Troubleshooting

**The backup fails with "Permission denied"**

This usually means the game has the save file locked while it's writing to it. The tool will log a warning but won't crash. It'll try again on the next backup cycle.

**The window freezes**

This shouldn't happen since backups run in a background thread. If it does, the source folder might be enormous or on a very slow drive.

## Building It Yourself

If you want to build the exe yourself instead of using the release:

1. Make sure you have Python 3.7+ installed

2. Install PyInstaller:
   ```
   pip install pyinstaller
   ```

3. Run this from the project folder:
   ```
   pyinstaller --onefile --noconsole autosave_manager.py
   ```

4. Your exe will be in the `dist` folder

The script itself has no dependencies outside of Python's standard library, so you can also just run `python autosave_manager.py` directly if you prefer.

## License

Do whatever you want with it.
