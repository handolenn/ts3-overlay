
#  TeamSpeak 3 Overlay

  

FiveM ile çalışan performans sorunu yaşatmayan TeamSpeak 3 Overlay'ı. 

  

---

  

##  1. TeamSpeak 3 Ayarı (Gerekli Tek Adım)

  

Uygulamanın TeamSpeak 3 ile doğrudan haberleşebilmesi için **ClientQuery** eklentisinin açık olması gereklidir:

  

1. TeamSpeak 3 uygulamasını açın.

2. Üst menüden **Tools (Araçlar) -> Options (Seçenekler)** sekmesine girin (Kısayol: `Alt + P`).

3. Sol menüden **Addons (Eklentiler)** kısmına tıklayın.

4. Listede **ClientQuery** eklentisini bulun ve durumunun **Enabled (Etkin)** olduğundan emin olun.

  

---

  

##  2. GitHub'dan İndirme & Kurulum

  

### Adım 1: Bilgisayarınıza Python indirin. 

- Bu program herhangi bir derleme işleminden geçmemiştir, açık kaynak kodlu olduğu için çalıştırabilmek için bilgisayarınızda Python'un [3.14.7](https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe) sürümü bulunmalı.  
- Python kurulumu esnasında  **`Add python.exe to PATH`** seçeneğinin seçili olduğundan emin olun! 

### Adım 2: GitHub'dan Projeyi İndirin

- Bu GitHub sayfasındaki yeşil **`Code`** butonuna tıklayıp **`Download ZIP`** seçeneğiyle bilgisayarınıza indirin ve klasöre çıkartın (veya `git clone` yapın).

  

### Adım 2: Gerekli Kütüphaneleri Yükleyin

- Komut satırını (CMD veya PowerShell) indirdiğiniz klasör içerisinde açın ve şu komutu çalıştırın:

```bash

pip install -r requirements.txt

```

- Bu tek seferliktir ve gerekli olan tüm kütüphaneleri kısa bir süre içinde yükleyecektir.
  

### Adım 3: Çalıştırın

- Klasör içerisindeki **`Overlay Aç.bat`** dosyasına çift tıklayarak uygulamayı kolayca başlatabilir veya komut satırından `python main.py` yazarak çalıştırabilirsiniz.
Teamspeak3 açık değilken çalışmayacaktır.


[youtube...](https://youtube.com/shorts/KTUq_7OETVQ)
