# UwU:3

Linux ve Termux (Android) için modern, renkli ve ayrıntılı terminal dosya yöneticisi.
Tek dosya (`uwu2.py`), sıfır bağımlılık: yalnızca Python 3.11+ standart kütüphanesi kullanır.

```
 UwU:3   /home/kullanici/Belgeler                         12 items
 ┌──────────────────────────────────────┬────────────────────────────────────┐
 │ + Projeler/                  <DIR>   │  ...önizleme...                    │
   notlar.txt              2.1 KB  ...  │                                    │
   resim.png               845 KB  ...  │                                    │
 └──────────────────────────────────────┴────────────────────────────────────┘
 drwxr-xr-x  kullanici  <DIR>  2026-11-23 23:40  | 3 selected | free 41.2 GB
 sort: name asc | hidden: off | preview: on              Ready. Press Ctrl+H.
 Ctrl+Q Quit  Ctrl+H Help  Enter Open  Space Select  Ctrl+C Copy  Ctrl+X Cut
 Ctrl+V Paste  Ctrl+D Trash  Ctrl+R Rename  Ctrl+N New  Ctrl+E Edit  Ctrl+F Filter
```

## Özellikler

| Özellik        | Ne yapar                                                                  |
| -------------- | ------------------------------------------------------------------------- |
| Gezinme        | Ok tuşları, vim tuşları (`hjkl`), sayfa kaydırma, geçmişte geri gitme    |
| Seçim          | Tek tek veya toplu seçim, seçim ile klasör değiştirme                    |
| Dosya işlemleri | Kopyala, kes, yapıştır, çoğalt, yeniden adlandır, sil (çöp kutusu ile) |
| Arşiv          | `.zip` ve `.tar` (`.tar.gz`, `.tgz` dahil) oluşturma ve açma             |
| Önizleme       | Metin dosyaları ve klasör içeriği için yan panel                         |
| Filtre         | Ada göre canlı filtreleme, `*` ve `?` joker karakterleri                  |
| Sıralama       | Ad, boyut, tarih veya uzantıya göre; artan/azalan                        |
| Yer imleri     | Sık kullanılan klasörleri kaydetme ve hızlıca açma                       |
| Detaylar       | Boyut, izinler, sahip, değiştirilme tarihi ve sembolik link hedefi      |
| Mouse          | Tıklayarak seçme, çift tıklayarak açma, tekerlek ile kaydırma            |
| Kabuk          | Bulunduğun klasörde kabuk komutu çalıştırma                               |

## Kurulum

Paket gerektirmez. Dosyayı indirip doğrudan çalıştırabilirsin:

```sh
python3 uwu2.py                 # geçerli klasörde açar
python3 uwu2.py ~/Indirilenler  # belirli bir klasörde açar
```

İstediğin yerden `uwu2` komutu olarak çalıştırmak için:

```sh
chmod +x uwu2.py
cp uwu2.py ~/.local/bin/uwu2
uwu2
```

Termux'ta:

```sh
pkg install python
python uwu2.py
```

Gereksinimler: Python 3.11+. Arayüz için `curses` gerekir; Linux ve Termux'ta varsayılan olarak bulunur.

## Kullanım

| Komut                  | Açıklama                              |
| ---------------------- | ------------------------------------- |
| `python3 uwu2.py`      | Geçerli klasörde aç                   |
| `python3 uwu2.py PATH` | Verilen klasörde aç                   |
| `--hidden`             | Açılışta gizli dosyaları göster       |
| `--no-preview`         | Açılışta önizleme panelini kapat      |
| `-V`, `--version`      | Sürümü göster                         |
| `-h`, `--help`         | Komut satırı yardımını göster         |

### Tuşlar

Alt kısımdaki çubuk en önemli tuşları gösterir. Tüm tuşlar için `Ctrl+H` tuşuna bas.

| Tuş                    | İşlev                                              |
| ---------------------- | -------------------------------------------------- |
| `Ctrl+Q` / `q`         | Çıkış                                              |
| `Ctrl+H` / `F1` / `?`  | Yardım sayfası                                     |
| `↑` `↓` / `j` `k`      | İmleci taşı                                        |
| `PgUp` / `PgDn`        | Sayfa sayfa kaydır                                 |
| `g` / `Home`, `G` / `End` | En başa / en sona git                           |
| `Enter` / `→` / `l`    | Klasörü aç, dosyayı varsayılan uygulamayla aç     |
| `←` / `h` / `Backspace`| Üst klasöre git                                    |
| `~`                    | Ana klasöre git                                    |
| `-`                    | Önceki klasöre dön                                 |
| `L` / `Ctrl+G`         | Yazarak yola git                                   |
| `Space`                | Seç / seçimi kaldır ve aşağı in                    |
| `a` / `Ctrl+A`         | Klasördeki tümünü seç                              |
| `u` / `Esc`            | Seçimi temizle (Esc filtreyi de temizler)          |
| `c` / `Ctrl+C`         | Kopyala                                            |
| `x` / `Ctrl+X`         | Kes                                                |
| `p` / `Ctrl+V`         | Yapıştır                                           |
| `y`                    | Yerinde çoğalt                                     |
| `d` / `Ctrl+D` / `Del` | Çöp kutusuna taşı                                  |
| `D`                    | Kalıcı olarak sil (onay ister)                     |
| `r` / `Ctrl+R` / `F2`  | Yeniden adlandır                                   |
| `n` / `Ctrl+N`         | Boş dosya oluştur                                  |
| `m` / `F7`             | Klasör oluştur                                     |
| `M`                    | İzinleri değiştir (sekizlik, ör. `755`)            |
| `Z`                    | Seçimi `.zip` olarak sıkıştır                      |
| `E`                    | Arşivi aç                                          |
| `e` / `Ctrl+E` / `F4`  | `$EDITOR` ile düzenle (yoksa nano, yoksa vi)       |
| `o`                    | Varsayılan uygulamayla aç (`xdg-open` / `termux-open`) |
| `i` / `F3`             | Ayrıntılar penceresi                               |
| `v`                    | Önizleme panelini aç / kapat                       |
| `/` / `Ctrl+F`         | Canlı filtre                                       |
| `s`                    | Sıralama ölçütünü değiştir                         |
| `S`                    | Sıralama yönünü tersine çevir                      |
| `.`                    | Gizli dosyaları göster / gizle                     |
| `Ctrl+L` / `F5`        | Klasörü yenile                                     |
| `b`                    | Bu klasörü yer imi olarak kaydet / kaldır          |
| `'` / `Ctrl+B`         | Yer imleri listesi (Enter ile git, `x` ile sil)    |
| `T`                    | Çöp kutusu klasörüne git                           |
| `!` / `Ctrl+T`         | Bu klasörde kabuk komutu çalıştır                  |

## Çöp kutusu

`d` ile silinen dosyalar `~/.local/share/uwu/trash` klasörüne taşınır. Oradan elle geri alabilirsin. Çöp kutusunun içinde `d` ile silinen öğeler kalıcı olarak silinir.

## Yapılandırma

Ayarlar `$XDG_CONFIG_HOME/uwu/config.json` dosyasında saklanır (yoksa `~/.config/uwu/config.json`). Dosya isteğe bağlıdır ve uygulama kapanırken otomatik yazılır.

```json
{
  "show_hidden": false,
  "sort_key": "name",
  "sort_reverse": false,
  "preview": true,
  "bookmarks": ["/home/kullanici/Belgeler"]
}
```

`sort_key` değerleri: `name`, `size`, `mtime` (tarih), `ext` (uzantı).

## Termux'ta notlar

- Dosyalara erişmek için önce `termux-setup-storage` komutunu çalıştır. Ardından `~/storage/shared` gibi klasörlere geçebilirsin.
- Dosyaları `o` ile açmak için `termux-open` komutu gerekir. Genellikle `pkg install termux-tools` ile gelir.

## Bilinen sınırlar

- Arama yalnızca geçerli klasördeki adlara göre yapılır; alt klasörlerde arama henüz yoktur.
- Bazı terminaller `Backspace` tuşunu `Ctrl+H` olarak gönderir. Bu durumda Backspace yardım sayfasını açabilir; üst klasöre gitmek için `←` veya `h` kullan.
- Büyük klasörlerde ve çok büyük dizinlerin boyut hesabında arayüz kısa süre yavaşlayabilir.

## Yol haritası

- Alt klasörlerde özyinelemeli arama
- Yan yana ikinci panel
- Dosya tipine göre simgeler (Nerd Font desteği ile)

---

*made by wortex213433*
