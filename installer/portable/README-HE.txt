Signal Viewer — גרסה ניידת ל-Windows
======================================

לא צריך להתקין כלום, ולא צריך אינטרנט. הכל נמצא בתיקייה הזו.

הפעלה
  1. חלצו את קובץ ה-ZIP לתיקייה כלשהי (למשל C:\SignalViewer).
     חשוב לחלץ — לא להפעיל מתוך ה-ZIP עצמו.
  2. לחיצה כפולה על:  Signal Viewer.bat
     האפליקציה נפתחת בחלון משלה תוך כמה שניות.

קיצור דרך בשולחן העבודה (פעם אחת)
  לחיצה כפולה על:  Create desktop shortcut.bat
  נוצר קיצור "Signal Viewer" עם האייקון של האפליקציה.
  אם מעבירים את התיקייה למקום אחר — מריצים אותו שוב.

אם Windows מציג אזהרה ("Windows protected your PC")
  זה קורה לקבצים שהורדו מהאינטרנט. לוחצים "More info" ואז "Run anyway".
  אפשר גם, לפני החילוץ: לחיצה ימנית על קובץ ה-ZIP > Properties > לסמן Unblock > OK.

אם משהו לא עובד
  לחיצה כפולה על:  Signal Viewer (troubleshooting).bat
  נפתח חלון שמציג את הודעת השגיאה. יומן מלא נשמר ב:
  %USERPROFILE%\.signalviewer\signalviewer.log

חלון האפליקציה
  החלון משתמש ברכיב WebView2 של Windows (מובנה ב-Windows 11 וב-Windows 10 מעודכן).
  אם הוא חסר, האפליקציה נפתחת בדפדפן (Edge/Chrome) — גם זה בלי אינטרנט.

מה יש בתיקייה
  runtime\   — Python 3.12 לWindows וכל הספריות (לא משפיע על Python אחר במחשב, אם יש)
  app\       — האפליקציה
