# iTunes-Playlist-Transfer
Exports a collection of playlists, from a given folder, and converts them to m3u8 files for transfer to Android

1. Reads an iTunes "Library.xml" file.
2. Finds a named playlist FOLDER inside it.
3. Exports every playlist inside that folder (including nested sub-folders)
   as a raw .m3u, using the same style as your manually-made playlists
   (M:\\Music\\Music\\... paths, "#EXTINF:<secs>,<Title> - <Artist>").
4. Converts each of those straight into the player's format
   (syncr/... paths, #EXTALB tags, UTF-8 .m3u8 with BOM) --
   same logic as convert_playlists.py.

Usage:
    python itunes_export.py --xml "G:\\Music\\iTunes Library.xml" --folder "U-playlists to export as m3u"

Optional:
    --raw-dir DIR         where the intermediate raw .m3u files are written
                          (default: ./raw_export)
    --output-dir DIR      where the final converted .m3u8 files are written
                          (default: ./converted)
    --no-recursive        only export playlists directly inside the folder,
                          not ones inside nested sub-folders
