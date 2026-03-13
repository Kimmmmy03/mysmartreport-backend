"""
MySmartReport — Gemini AI Service

Uses the google-genai SDK.
Passes AI response text directly into the template without formatting.
"""

import asyncio
import json
import re
from google import genai
from config import settings, build_system_prompt


def _extract_field(data: dict, *keys) -> str:
    """Extract a field from AI response, trying multiple possible key names."""
    for key in keys:
        val = data.get(key)
        if val is not None and val != "":
            if isinstance(val, list):
                return "\n".join(str(item) for item in val)
            return str(val).strip()
    return ""


# Exact exception-week labels as defined in the system prompt.
# Weeks whose topik matches any of these must NOT be enriched.
EXCEPTION_WEEK_LABELS: tuple[str, ...] = (
    "CUTI PERTENGAHAN SEMESTER IPG",
    "MINGGU ULANGKAJI",
    "PEPERIKSAAN AKHIR",
    "CUTI AKHIR SEMESTER IPG",
)


def is_exception_week(topik: str) -> bool:
    """Return True if the topik is an exception-week label (holiday / exam / break)."""
    t = topik.strip().upper()
    return any(label in t or t in label for label in EXCEPTION_WEEK_LABELS)


def _build_prompt(topik: str, minggu: int) -> str:
    """Build a Bahasa Melayu prompt for a single week with session-type-contextual refleksi."""
    return (
        f"Topik Minggu {minggu}: {topik}\n\n"
        "Berdasarkan topik di atas, sila berikan dalam format JSON.\n"
        "JSON MESTI mempunyai LIMA kunci sahaja: hasil_pembelajaran, strategi, refleksi_kuliah, refleksi_tutorial, refleksi_epembelajaran\n"
        "Setiap nilai MESTI berupa STRING (teks biasa), BUKAN array atau list.\n\n"
        "Contoh format jawapan (IKUT PANJANG DAN GAYA INI):\n"
        "{\n"
        '  "hasil_pembelajaran": "Pada akhir sesi ini, pelajar dapat:\\n'
        "i. Menjelaskan definisi dan konsep asas topik ini berdasarkan pandangan tokoh-tokoh utama dalam bidang pendidikan dengan merujuk kepada konteks pendidikan di Malaysia\\n"
        "ii. Menghuraikan ciri-ciri utama dan prinsip-prinsip yang mendasari topik ini secara terperinci dengan memberikan contoh-contoh yang relevan dalam situasi bilik darjah\\n"
        "iii. Menganalisis hubungan antara teori dan amalan dalam konteks pengajaran dan pembelajaran di sekolah rendah dengan membuat perbandingan antara pendekatan yang berbeza\\n"
        "iv. Mengaplikasikan pengetahuan topik ini dalam merancang aktiviti pengajaran dan pembelajaran yang berkesan serta sesuai dengan tahap perkembangan murid\\n"
        'v. Menilai kepentingan topik ini dalam pembangunan profesionalisme guru dan perkembangan murid secara holistik merangkumi aspek kognitif, afektif dan psikomotor",\n'
        '  "strategi": "Kuliah\\n'
        "- Pensyarah memulakan sesi dengan tayangan slaid berkaitan definisi dan konsep utama topik. Perbincangan interaktif dijalankan untuk mengaitkan konsep dengan pengalaman sedia ada pelajar. Pensyarah menggunakan teknik penyoalan untuk merangsang pemikiran kritis.\\n"
        "- Pensyarah menerangkan teori-teori dan pandangan tokoh utama menggunakan peta minda di papan putih. Pelajar diminta mencatat nota dalam bentuk grafik organizer dan bertanya soalan untuk penjelasan lanjut.\\n"
        "- Aktiviti soal jawab dijalankan secara berstruktur menggunakan teknik Think-Pair-Share. Pensyarah mengemukakan soalan aras tinggi berdasarkan Taksonomi Bloom untuk menguji kefahaman dan kemahiran analisis pelajar.\\n"
        "- Pensyarah menunjukkan video pendek atau kajian kes berkaitan aplikasi topik dalam konteks sebenar bilik darjah di Malaysia. Perbincangan kelas dijalankan untuk menganalisis kekuatan dan kelemahan pendekatan yang ditunjukkan.\\n"
        "- Pensyarah membuat rumusan keseluruhan dan mengaitkan topik dengan isu semasa dalam pendidikan di Malaysia serta implikasi terhadap amalan pengajaran guru.\\n\\n"
        "Tutorial\\n"
        "- Pelajar dibahagikan kepada kumpulan kecil (4-5 orang) untuk membincangkan soalan tugasan berkaitan topik minggu ini. Setiap ahli kumpulan diberikan peranan khusus (ketua, pencatat, pembentang, pemasa).\\n"
        "- Setiap kumpulan menyediakan peta minda atau poster ringkas yang merumuskan poin-poin utama topik dan mengaitkannya dengan pengalaman praktikum atau pemerhatian di sekolah.\\n"
        "- Pembentangan kumpulan dijalankan selama 5-7 minit setiap kumpulan, diikuti sesi soal jawab dan maklum balas daripada kumpulan lain untuk menggalakkan pembelajaran kolaboratif.\\n"
        "- Aktiviti refleksi bertulis: pelajar menulis 3 perkara utama yang dipelajari, 2 persoalan yang timbul, dan 1 cara untuk mengaplikasikan ilmu dalam konteks pengajaran sebenar.\\n"
        '- Pensyarah memberi maklum balas konstruktif dan mengukuhkan pemahaman pelajar melalui perbincangan bersama serta memberi tugasan bacaan untuk minggu seterusnya.\\n\\n'
        "E-pembelajaran\\n"
        "- Pelajar diminta menyertai forum perbincangan dalam talian melalui Google Classroom berkaitan topik minggu ini. Setiap pelajar perlu menghantar sekurang-kurangnya satu posting asal dan dua respons kepada rakan sekelas.\\n"
        "- Kuiz interaktif menggunakan Kahoot atau Quizziz dijalankan untuk menguji kefahaman pelajar terhadap konsep utama topik. Markah kuiz digunakan sebagai penilaian formatif.\\n"
        '- Pelajar membina infografik atau peta minda digital menggunakan Canva berdasarkan rumusan topik minggu ini dan berkongsi melalui Padlet kelas untuk semakan rakan sebaya.",\n'
        '  "refleksi_kuliah": "Sesi kuliah minggu ini memberi tumpuan kepada penguasaan ilmu teoritikal yang mendalam berkaitan topik yang diajar. '
        "Pelajar didedahkan kepada konsep-konsep teras dan prinsip asas yang menjadi landasan kepada pemahaman subjek ini secara menyeluruh, dengan pensyarah menghuraikan setiap konsep menggunakan contoh-contoh berasaskan konteks pendidikan Malaysia yang relevan. "
        "Sesi syarahan berlangsung dengan lancar di mana pelajar menunjukkan penglibatan yang aktif melalui respon positif dalam sesi soal jawab interaktif, membuktikan kefahaman mereka terhadap kandungan teori yang disampaikan. "
        "Walau bagaimanapun, sebilangan pelajar masih memerlukan bimbingan tambahan dalam menghubungkaitkan kerangka teoritikal dengan situasi praktikal di bilik darjah, dan pensyarah perlu merancang lebih banyak ilustrasi konkrit untuk kumpulan ini. "
        "Penggunaan pelbagai bahan bantu mengajar seperti tayangan slaid, rajah konsep, dan petikan daripada tokoh pendidikan berjaya memperkukuh pemahaman pelajar terhadap prinsip-prinsip yang diajar. "
        'Bagi sesi akan datang, pensyarah merancang untuk mengintegrasikan lebih banyak kajian kes berasaskan senario sebenar supaya ilmu teoritikal dapat diterjemahkan dengan lebih berkesan kepada amalan pengajaran.",\n'
        '  "refleksi_tutorial": "Sesi tutorial minggu ini direka bentuk untuk mengukuhkan penerapan teori melalui aktiviti hands-on dan perbincangan berkumpulan yang sistematik. '
        "Pelajar bekerja dalam kumpulan kecil untuk menyelesaikan tugasan yang memerlukan mereka mengaplikasikan konsep daripada sesi kuliah kepada senario pengajaran yang realistik, menggalakkan pemikiran kritikal dan kolaboratif secara serentak. "
        "Kebanyakan kumpulan berjaya mengemukakan penyelesaian yang kreatif dan berasas teori semasa sesi pembentangan, menunjukkan bahawa pelajar mampu mengintegrasikan pembelajaran teoritikal dengan pemikiran amali yang praktikal. "
        "Namun, beberapa kumpulan masih menghadapi cabaran dalam membahagikan peranan secara adil dan mengurus masa pembentangan dengan cekap, aspek yang perlu ditingkatkan dalam sesi tutorial akan datang. "
        "Aktiviti penyelesaian masalah berstruktur yang dijalankan semasa tutorial berjaya merangsang diskusi mendalam dan menghasilkan pelbagai perspektif yang memperkayakan pengalaman pembelajaran semua pelajar. "
        'Pensyarah akan menambah baik reka bentuk tugasan tutorial dengan memasukkan lebih banyak situasi dilema dan soalan terbuka bagi mencabar pelajar berfikir di luar kerangka teori yang telah dipelajari.",\n'
        '  "refleksi_epembelajaran": "Sesi e-pembelajaran minggu ini memberikan peluang kepada pelajar untuk meneroka dan menguasai kandungan secara kendiri menggunakan sumber digital yang disediakan melalui platform pembelajaran dalam talian. '
        "Pelajar menunjukkan tahap penyertaan yang menggalakkan dalam forum perbincangan Google Classroom, dengan majoriti pelajar menghantar posting yang bernas dan memberikan respons yang membina kepada rakan sekelas mengikut tempoh yang ditetapkan. "
        "Penggunaan platform digital seperti Kahoot dan Canva berjaya meningkatkan motivasi pelajar dan mendorong mereka meneroka konsep secara lebih mendalam berbanding kaedah pembelajaran tradisional yang pasif. "
        "Namun, beberapa pelajar menghadapi kesukaran teknikal dalam mengakses platform disebabkan masalah capaian internet, dan ini menjadi penghalang kepada pengalaman e-pembelajaran yang seragam bagi semua pelajar. "
        "Disiplin diri dan kemahiran pengurusan masa pelajar turut diuji dalam sesi e-pembelajaran ini, memandangkan mereka perlu mengurus pembelajaran secara autonomi tanpa pengawasan langsung daripada pensyarah. "
        'Penambahbaikan pada masa hadapan termasuk menyediakan panduan penggunaan platform yang lebih terperinci serta mewujudkan mekanisme sokongan rakan sebaya dalam talian bagi membantu pelajar yang menghadapi kekangan teknikal atau kefahaman."\n'
        "}\n\n"
        "PERATURAN PENTING:\n"
        "- hasil_pembelajaran: Bermula dengan 'Pada akhir sesi ini, pelajar dapat:' "
        "diikuti 5-6 poin menggunakan penomboran Roman kecil (i. ii. iii. iv. v. vi.). "
        "DILARANG menggunakan '- ' atau bullet point untuk hasil pembelajaran. WAJIB guna i. ii. iii. iv. v. vi. sahaja. "
        "SETIAP POIN mesti PANJANG (sekurang-kurangnya 20 patah perkataan), "
        "SPESIFIK kepada topik minggu ini, dan merujuk konteks pendidikan Malaysia/IPG. "
        "Gunakan kata kerja Taksonomi Bloom: menjelaskan, menghuraikan, menganalisis, "
        "mengaplikasikan, menilai, membanding, mengkategorikan, merumuskan.\n"
        "- strategi: WAJIB ada bahagian Kuliah, Tutorial, DAN E-pembelajaran. "
        "Kuliah mesti ada 5-6 aktiviti, Tutorial mesti ada 4-5 aktiviti, dan E-pembelajaran mesti ada 3-4 aktiviti. "
        "SETIAP aktiviti mesti PANJANG (sekurang-kurangnya 25 patah perkataan). "
        "Nyatakan kaedah SPESIFIK dan BAGAIMANA aktiviti dijalankan. "
        "Gunakan kaedah: tayangan slaid, peta minda, video, kajian kes, main peranan, "
        "pembentangan poster, Think-Pair-Share, perbincangan berkumpulan, soal jawab berstruktur, simulasi.\n"
        "- E-pembelajaran dalam strategi: Gunakan platform digital seperti Google Classroom, Padlet, Kahoot, Quizziz, Canva, Mentimeter, Flipgrid, atau Edpuzzle.\n"
        "- refleksi_kuliah: MESTI 1-2 perenggan PANJANG (sekurang-kurangnya 6-7 ayat). "
        "FOKUS EKSKLUSIF pada aspek teoritikal: penguasaan ilmu, konsep teras yang diperkenalkan, prinsip-prinsip asas, dan bagaimana pengetahuan asas ini berkaitan dengan bidang subjek yang lebih luas. "
        "Nyatakan respons pelajar terhadap kaedah penyampaian teori, tahap kefahaman konsep abstrak, dan cadangan konkrit untuk memperkukuh pengajaran teori pada sesi akan datang.\n"
        "- refleksi_tutorial: MESTI 1-2 perenggan PANJANG (sekurang-kurangnya 6-7 ayat). "
        "FOKUS EKSKLUSIF pada aspek praktikal: penerapan teori melalui latihan, perbincangan kumpulan, aktiviti hands-on, dan bagaimana pelajar menggunakan teori daripada kuliah untuk menyelesaikan senario praktikal. "
        "Nyatakan kualiti penyelesaian masalah, kemahiran kolaboratif, dinamika kumpulan, dan strategi untuk meningkatkan kualiti tutorial akan datang.\n"
        "- refleksi_epembelajaran: MESTI 1-2 perenggan PANJANG (sekurang-kurangnya 6-7 ayat). "
        "FOKUS EKSKLUSIF pada aspek pembelajaran kendiri digital: navigasi platform, pembelajaran bersendiri, keberkesanan sumber digital, disiplin diri, dan pengalaman kefahaman secara autonomi. "
        "Nyatakan kadar penyertaan dalam talian, kualiti hasil kerja digital, cabaran teknikal, dan cadangan untuk meningkatkan pengalaman e-pembelajaran.\n"
        "- SETIAP refleksi (Kuliah, Tutorial, E-pembelajaran) MESTI berbeza sepenuhnya dalam isi dan tumpuan. DILARANG mengulang ayat, frasa, atau idea yang sama antara ketiga-tiga refleksi.\n"
        "- PENTING: Setiap refleksi MESTI PANJANG dan SUBSTANTIF (sekurang-kurangnya 1-2 perenggan penuh). JANGAN ringkas atau beri jawapan generik.\n"
        "- Bahasa Melayu akademik\n"
        "- JANGAN tinggalkan mana-mana kunci kosong"
    )


async def enrich_week(topik: str, minggu: int, nama_kursus: str = "", program: str = "", detail_level: str = "normal") -> dict:
    """
    Call Gemini API to enrich a single week's content.
    Returns dict with hasil_pembelajaran, strategi_aktiviti, refleksi, refleksi_tutorial, refleksi_epembelajaran.
    Holiday/break weeks (blank topik) return empty strings — no fabricated content.
    """
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your-gemini-api-key-here":
        return {
            "hasil_pembelajaran": f"Hasil pembelajaran untuk Minggu {minggu} (API key belum dikonfigurasi)",
            "strategi_aktiviti": f"Strategi aktiviti untuk Minggu {minggu} (API key belum dikonfigurasi)",
            "refleksi": f"Refleksi untuk Minggu {minggu} (API key belum dikonfigurasi)",
            "refleksi_tutorial": f"Refleksi tutorial untuk Minggu {minggu} (API key belum dikonfigurasi)",
            "refleksi_epembelajaran": f"Refleksi e-pembelajaran untuk Minggu {minggu} (API key belum dikonfigurasi)",
        }

    # CRITICAL: Holiday/exam/break weeks must NOT be enriched.
    # They keep their exception label in topik_tajuk; all enrichment fields stay empty.
    effective_topik = topik.strip() if topik else ""
    if not effective_topik or is_exception_week(effective_topik):
        return {
            "hasil_pembelajaran": "",
            "strategi_aktiviti": "",
            "refleksi": "",
            "refleksi_tutorial": "",
            "refleksi_epembelajaran": "",
        }

    prompt = _build_prompt(effective_topik, minggu)
    system_prompt = build_system_prompt(nama_kursus, program, detail_level)

    MAX_RETRIES = 2
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Adjust token limit based on detail level
    token_limits = {"normal": 4096, "terperinci": 10240}
    max_tokens = token_limits.get(detail_level, 8192)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.5,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                ),
            )

            raw_text = response.text
            print(f"[Gemini RAW] Week {minggu} (attempt {attempt}): {raw_text[:200]}")

            data = json.loads(raw_text)
            print(f"[Gemini KEYS] Week {minggu}: {list(data.keys())}")

            # Extract fields — try multiple possible key names
            hasil = _extract_field(data,
                "hasil_pembelajaran", "hasilPembelajaran", "hasil",
                "learning_outcomes", "outcomes")
            strategi = _extract_field(data,
                "strategi", "strategi_aktiviti", "strategiAktiviti",
                "strategi_pengajaran", "aktiviti", "strategy", "activities")
            refleksi_kuliah = _extract_field(data,
                "refleksi_kuliah", "refleksi", "reflection", "catatan_refleksi")
            refleksi_tutorial = _extract_field(data,
                "refleksi_tutorial")
            refleksi_epembelajaran = _extract_field(data,
                "refleksi_epembelajaran", "refleksi_e_pembelajaran",
                "refleksi_elearning", "e_pembelajaran")

            print(f"[Gemini PARSED] Week {minggu}: hasil={len(hasil)} chars, "
                  f"strategi={len(strategi)} chars, refleksi_kuliah={len(refleksi_kuliah)} chars, "
                  f"refleksi_tutorial={len(refleksi_tutorial)} chars, "
                  f"refleksi_epembelajaran={len(refleksi_epembelajaran)} chars")

            if not refleksi_kuliah:
                refleksi_kuliah = f"Pelajar dapat memahami topik Minggu {minggu} dengan baik."
            if not refleksi_tutorial:
                refleksi_tutorial = refleksi_kuliah
            if not refleksi_epembelajaran:
                refleksi_epembelajaran = f"Pelajar menunjukkan penglibatan yang baik dalam aktiviti e-pembelajaran Minggu {minggu}."

            return {
                "hasil_pembelajaran": hasil or f"Hasil pembelajaran Minggu {minggu}",
                "strategi_aktiviti": strategi or f"Kuliah\nPerbincangan topik Minggu {minggu}\n\nTutorial\nLatihan dan pembentangan\n\nE-pembelajaran\nForum perbincangan dalam talian",
                "refleksi": refleksi_kuliah,
                "refleksi_tutorial": refleksi_tutorial,
                "refleksi_epembelajaran": refleksi_epembelajaran,
            }

        except json.JSONDecodeError as e:
            print(f"[Gemini JSON Error] Week {minggu} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                print(f"[Gemini Retry] Retrying Week {minggu}...")
                await asyncio.sleep(2)
                continue
            # Final attempt failed — return fallback
            print(f"[Gemini Fallback] Week {minggu}: returning generic content after {MAX_RETRIES} failed attempts")
            return {
                "hasil_pembelajaran": f"Hasil pembelajaran Minggu {minggu}",
                "strategi_aktiviti": f"Kuliah\nPerbincangan topik Minggu {minggu}\n\nTutorial\nLatihan dan pembentangan\n\nE-pembelajaran\nForum perbincangan dalam talian",
                "refleksi": f"Pelajar dapat memahami topik Minggu {minggu} dengan baik.",
                "refleksi_tutorial": f"Pelajar dapat memahami topik Minggu {minggu} dengan baik.",
                "refleksi_epembelajaran": f"Pelajar menunjukkan penglibatan yang baik dalam aktiviti e-pembelajaran Minggu {minggu}.",
            }

        except Exception as e:
            error_msg = str(e)[:80]
            print(f"[Gemini Error] Week {minggu}: {e}")
            return {
                "hasil_pembelajaran": f"Ralat AI - Minggu {minggu}: {error_msg}",
                "strategi_aktiviti": "",
                "refleksi": "",
                "refleksi_tutorial": "",
                "refleksi_epembelajaran": "",
            }

    # Should not reach here, but safety fallback
    return {
        "hasil_pembelajaran": f"Hasil pembelajaran Minggu {minggu}",
        "strategi_aktiviti": "",
        "refleksi": "",
        "refleksi_tutorial": "",
        "refleksi_epembelajaran": "",
    }


async def extract_file_content(raw_text: str) -> dict:
    """
    Use Gemini to extract metadata and weekly data from raw file text.
    Returns dict with 'metadata' and 'weeks' keys.
    """
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your-gemini-api-key-here":
        raise ValueError("Gemini API key not configured")

    prompt = (
        "Anda adalah pakar dalam membaca dokumen rancangan pengajaran IPG (Institut Pendidikan Guru).\n"
        "Berikut adalah kandungan fail silabus/rancangan pengajaran.\n"
        "Data disusun sebagai 'label : nilai'. Setiap baris mengandungi satu atau lebih pasangan label-nilai.\n\n"
        "KANDUNGAN FAIL:\n"
        f"{raw_text}\n\n"
        "TUGAS ANDA: Ekstrak SEMUA maklumat di bawah. Baca SETIAP baris dengan teliti.\n\n"
        "MEDAN METADATA YANG PERLU DICARI:\n"
        "- program: Cari perkataan 'PROGRAM' diikuti oleh nama program (cth: PISMP, PDPP)\n"
        "- semester: Cari perkataan 'SEMESTER' diikuti oleh nombor semester\n"
        "- tahun: Cari perkataan 'TAHUN' diikuti oleh tahun akademik (cth: 2025/2026)\n"
        "- pensyarah: Cari perkataan 'NAMA PENSYARAH' atau 'PENSYARAH' diikuti oleh nama penuh\n"
        "- ambilan: Cari perkataan 'AMBILAN' diikuti oleh nilai ambilan\n"
        "- jabatan: Cari perkataan 'JABATAN' atau 'UNIT' diikuti oleh nama jabatan\n"
        "- kumpulan_diajar: Cari 'KUMPULAN DIAJAR' diikuti oleh senarai kumpulan (boleh >1, pisahkan jadi array)\n"
        "- nama_kursus: Cari 'NAMA KURSUS' diikuti oleh nama penuh kursus\n"
        "- kod_kursus: Cari 'KOD KURSUS' diikuti oleh kod (format EDUP1234, KPD1234, dsb)\n"
        "- jumlah_kredit: Cari 'JUMLAH KREDIT' atau 'KREDIT' diikuti oleh nombor kredit\n\n"
        "PENTING: Dalam fail ini, label dan nilai SELALUNYA dipisahkan oleh ' : '. "
        "Contoh baris: 'NAMA PENSYARAH : Dr. Ahmad bin Ali : AMBILAN : Jun 2024' "
        "bermaksud pensyarah='Dr. Ahmad bin Ali' dan ambilan='Jun 2024'.\n\n"
        "ARAHAN MINGGUAN (KRITIKAL):\n"
        "Ekstrak TEPAT 19 minggu (Minggu 1 hingga Minggu 19). "
        "Setiap minggu MESTI ada entri dalam array 'weeks'.\n"
        "Untuk setiap minggu, ekstrak tarikh dan topik/tajuk.\n"
        "PERHATIAN KHAS — MINGGU 1: Jika label 'Minggu 1' tidak jelas, cari padanan alternatif seperti "
        "'Week 1', 'Bab 1', 'Chapter 1', atau entri pertama dalam jadual pengajaran.\n\n"
        "PENGENDALIAN MINGGU PENGECUALIAN (WAJIB IKUT):\n"
        "Jika sesuatu minggu jatuh pada mana-mana pengecualian berikut, "
        "WAJIB sertakan minggu tersebut dengan nombor minggu dan tarikh, "
        "dan letakkan label pengecualian yang TEPAT sebagai nilai 'topik':\n"
        "  * 'CUTI PERTENGAHAN SEMESTER IPG'\n"
        "  * 'MINGGU ULANGKAJI'\n"
        "  * 'PEPERIKSAAN AKHIR'\n"
        "  * 'CUTI AKHIR SEMESTER IPG'\n"
        "JANGAN kosongkan topik untuk minggu pengecualian — gunakan label tepat di atas.\n"
        "JANGAN hasilkan hasil_pembelajaran atau aktiviti untuk minggu pengecualian.\n\n"
        "Pulangkan JSON:\n"
        "{\n"
        '  "metadata": {\n'
        '    "program": "", "semester": "", "tahun": "", "pensyarah": "",\n'
        '    "ambilan": "", "jabatan": "", "kumpulan_diajar": [],\n'
        '    "nama_kursus": "", "kod_kursus": "", "jumlah_kredit": ""\n'
        "  },\n"
        '  "weeks": [{"minggu": 1, "tarikh": "", "topik": "", "jam": "", "catatan": ""}]\n'
        "}\n\n"
        "PERATURAN AKHIR:\n"
        "- WAJIB isi SEMUA 10 medan metadata. Baca fail dari awal hingga akhir.\n"
        "- kumpulan_diajar MESTI array of strings\n"
        "- minggu MESTI integer, julat 1 hingga 19\n"
        "- WAJIB hasilkan TEPAT 19 entri dalam array 'weeks' (Minggu 1 - Minggu 19)\n"
        "- Topik untuk minggu pengajaran biasa MESTI lengkap, JANGAN pendekkan\n"
        "- Tarikh: ambil TARIKH MULA sahaja. Contoh: '1/1/2026 - 7/1/2026' -> tulis '1/1/2026'\n"
        "- Pulangkan JSON sahaja"
    )

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8000,
                response_mime_type="application/json",
            ),
        )

        raw_response = response.text
        print(f"[Gemini Extract] Response length: {len(raw_response)} chars")

        # Sanitize Gemini's JSON response (trailing commas, markdown fences, etc.)
        cleaned = raw_response.strip()
        # Remove markdown code fences if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        # Remove trailing commas before } or ]
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
        # Strip any trailing whitespace/newlines
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        print(f"[Gemini Extract] Keys: {list(data.keys())}")

        if "metadata" not in data or "weeks" not in data:
            raise ValueError("Response missing 'metadata' or 'weeks' keys")

        return data

    except Exception as e:
        print(f"[Gemini Extract Error] {e}")
        raise


async def enrich_all_weeks(weeks: list[dict], nama_kursus: str = "", program: str = "") -> list[dict]:
    """
    Enrich all weeks sequentially (one by one) to avoid rate limits.
    """
    enriched = []
    for week in weeks:
        result = await enrich_week(
            week["topik"], week["minggu"],
            nama_kursus=nama_kursus, program=program
        )
        week.update(result)
        enriched.append(week)
        # Small delay between requests to avoid rate limits
        if len(weeks) > 1:
            await asyncio.sleep(1)

    return enriched
