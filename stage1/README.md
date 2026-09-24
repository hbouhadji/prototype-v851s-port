# V85x stage 1 — Linux en RAM, BusyBox et console USB

État au 25 septembre 2026 : **validé sur le dongle**. Les 128 Mio passent deux tests complets sans cache/MMU, Linux 6.13-rc1 démarre en RAM et le shell BusyBox répond par `g_serial` sur `/dev/cu.usbmodem1101`. Le journal `logs/usb-shell.log` contient `uname`, `/proc/meminfo`, les logs de démarrage et un marqueur de commande unique.

**État actuel de la flash : le 24 septembre 2026, à la demande explicite de l’utilisateur, la partition boot0 (premier Mio) a été sauvegardée puis effacée pour permettre le retour automatique en FEL.** La relecture confirme 1 Mio entièrement à `0xff` et les 3 Mio d’U-Boot strictement inchangés. Après `xfel reset`, FEL répond avec `ID=0x00188600`, scratchpad `0x00040400`. Le retour automatique en FEL après coupure physique est également confirmé le 25 septembre 2026. Le firmware d’origine ne peut plus démarrer tant que boot0 n’est pas restauré. Voir [sauvegarde et restauration](BOOT0-RECOVERY.md).

Le FES V0.16 atteignait la fin de son initialisation, mais les lectures mémoire bloquaient. Le pilote C V0.24 d’awboot fonctionne avec les paramètres du boot0 original ; voir [son adaptation SRAM](boot/awboot/README.md). Le chargement du boot0 natif à `0x20000` reste désactivé après un blocage pendant son transfert. Les essais antérieurs sont conservés dans [l’historique](EXPERIMENT-HISTORY.md).

## Sources et construction

- Linux [v6.13-rc1](https://github.com/torvalds/linux/tree/v6.13-rc1), archive dans `downloads/`.
- Patch `linux-6.13-rc1-wip.patch` d’[awboot 5380c00f](https://github.com/szemzoa/awboot/tree/5380c00fc67c975433f25c57fb481aa2b91aebf8), appliqué sans rejet.
- Ajout local de `allwinner,sun8i-v853` à la liste des machines ARM (`configs/0001-v853-machine.patch`).
- BusyBox 1.37.0, statique ARM EABI hard-float. Accélérations SHA x86 désactivées pour cette compilation ARM.
- [xfel 445e8aef](https://github.com/xboot/xfel/tree/445e8aefe6914c85817cc9bd1d201629364b0ec6), à placer dans `src/xfel` et à modifier avec `configs/0002-xfel-usb-timeout.patch` pour le test mémoire long.
- Le chemin matériel validé utilise le pilote DDR C d’awboot en SRAM. Les diagnostics antérieurs utilisent aussi un initialiseur extrait de xfel avec les 24 paramètres du boot0.
- Trampoline ARM minimal fondé sur le protocole de démarrage Linux et les registres V85x utilisés par awboot. Il préserve la DRAM, traite les caches et remet l’USB à zéro ; il ne reprend pas le chemin PSCI T113 du `main.c` actuel d’awboot.

La compilation Linux utilise un conteneur Debian ARM64 avec `arm-linux-gnueabihf-gcc`. Le build natif des petits programmes SRAM utilise `arm-none-eabi-gcc` sur macOS.

Depuis la racine du projet :

```sh
docker build -t v851s-stage1-builder stage1
docker run --rm --name v851s-stage1-build \
  -v "$PWD/stage1:/work" v851s-stage1-builder bash tools/build-linux.sh
bash stage1/tools/build-sram.sh
bash stage1/tools/build-awboot-ddr.sh
make -C stage1/src/xfel -j4
cp stage1/src/xfel/xfel stage1/tools/xfel
python3 stage1/tools/prepare-ddr.py stage1/boot/xfel-v851_v853.c \
  firmware-128MiB.bin stage1/out/ddr-stock.bin
```

`build-linux.sh` attend les archives déjà extraites dans `src/` et le patch awboot déjà appliqué. Pour repartir d’une extraction neuve :

```sh
tar -xzf stage1/downloads/linux-v6.13-rc1.tar.gz -C stage1/src
tar -xjf stage1/downloads/busybox-1.37.0.tar.bz2 -C stage1/src
patch -d stage1/src/linux-6.13-rc1 -p1 < stage1/downloads/linux-6.13-rc1-wip.patch
git clone https://github.com/xboot/xfel.git stage1/src/xfel
git -C stage1/src/xfel checkout 445e8aefe6914c85817cc9bd1d201629364b0ec6
patch -d stage1/src/xfel -p1 < stage1/configs/0002-xfel-usb-timeout.patch
```

Les archives Linux 6.13-rc1 et BusyBox 1.37.0 sont à obtenir avant ces commandes ; leurs SHA-256 figurent dans `downloads/SHA256SUMS`. Le dépôt Git exclut les sources téléchargées, les binaires construits et le dump NAND. Les sauvegardes boot0/U-Boot restent locales : leur présence et leur somme SHA-256 doivent être contrôlées avant toute restauration.

Les options indispensables sont contrôlées avant compilation. MTD, SPI, MMC et les modules sont désactivés. Le système racine est un initramfs ; `/init` monte les pseudo-systèmes de fichiers et ouvre un shell sur `ttyGS0`.

## Essais matériels, dans cet ordre

Ces commandes sont des opérations **RAM/SRAM uniquement**. Le test mémoire remplace le contenu volatile ; un retour au firmware d’origine nécessite un redémarrage. Ne pas les exécuter en parallèle avec un autre outil FEL.

```sh
python3 stage1/tools/ram-boot.py inspect
python3 stage1/tools/ram-boot.py ddr-awboot
python3 stage1/tools/ram-boot.py test-ram
python3 stage1/tools/ram-boot.py boot
```

`ddr-awboot` vérifie le chargement du pilote C à `0x28000`, l’exécute, puis vérifie trois régions DRAM distinctes. Le watchdog couvre son exécution ; sept attentes de registres sont bornées à 100 ms. `test-ram` effectue deux passes complètes, motifs adresse XOR masque et son complément, sur les 128 Mio avec cache de données/MMU désactivés. Il refuse de valider un résultat incomplet ou un mode CPU inattendu. Son résultat est dans `logs/ram-test-result.json`, puis `logs/ram-validated.json` en cas de succès.

`boot` exige la preuve du test et son marqueur encore présent en RAM. Chaque image envoyée est relue et comparée octet par octet. Les plages mémoire sont bornées. Le manifeste du dernier essai est dans `logs/last-boot-images.json`.

| Objet | Adresse | Borne |
| --- | --- | --- |
| Initialiseur DDR, test SRAM ou trampoline, successivement | `0x00028000` | Code avant `0x0003b000` |
| Pile SRAM du test et du trampoline | `0x0003c000` | Descendante |
| Résultat SRAM du test / jalon du trampoline | `0x0003d000` | 28 octets pour le test |
| Zone de travail FEL annoncée par le SoC | `0x00040400` | Ne pas recouvrir |
| Noyau décompressé | `0x40008000` | Vérification de taille avant le zImage |
| zImage | `0x42000000` | Avant `0x43000000` |
| DTB | `0x43000000` | 1 Mio maximum |
| Initramfs externe | `0x44000000` | Avant `0x47f00000` |
| Marqueur de validation mémoire | `0x47fff000` | 32 octets |

Le gadget ACM attendu utilise `0525:a4a7`. Sur macOS, chercher un nouveau `/dev/cu.usbmodem*`. La disparition de `1f3a:efe8` seule n’est pas un succès. Il faut lire la bannière puis exécuter `uname -a`, `cat /proc/meminfo`, `dmesg` et une commande avec une sortie identifiable.

## Vérifications déjà faites et limites

- Le patch s’applique et Linux compile avec CCU V853, pinctrl, PHY USB, MUSB Sunxi, `g_serial`, console série gadget et timer ARM.
- BusyBox est un exécutable ARM statique sans segment INTERP.
- L’archive initramfs contient `/init` exécutable, les liens BusyBox nécessaires, `/dev/console` (5,1) et `/dev/null` (1,3).
- Le pilote DDR C fait 8 616 octets ; les autres programmes SRAM restent dans leurs régions réservées.
- Les adresses USB/reset proviennent des pilotes et du patch V853. La transition FEL → gadget est validée sur le dongle ; le watchdog est armé pendant le lancement et `/init` l’arrête une fois le gadget USB configuré par l’hôte.
- Le code Linux conserve les horloges non utilisées (`clk_ignore_unused`). Le timer ARM est validé à 24 MHz. La DDR utilise les paramètres 936 MHz du firmware ; les autres périphériques ne sont pas validés par cet essai.
- Le dump complet et le boot0 ne sont jamais exécutés tels quels : le chemin actuel utilise le pilote DDR C d’awboot, avec les paramètres du boot0.

## Résultat matériel du 25 septembre 2026

- DDR awboot V0.24 : 128 Mio, trois régions de 4 Kio vérifiées et relues sans alias.
- Test SRAM : deux passes adresse XOR masque sur `0x40000000..0x47ffffff`, PASS, phase 4, cache de données/MMU désactivés. Le marqueur de session est relu avant lancement.
- Noyau : `Linux (none) 6.13.0-rc1-v851s-ram-stage1`, ARMv7 Cortex-A7, timer physique 24 MHz.
- `/init` démarre vers 0,69 seconde dans le journal noyau ; le gadget série est prêt vers 0,65 seconde.
- Mémoire Linux : `MemTotal: 124412 kB`, sur 128 Mio physiques, après réservations noyau et 1 Mio de ramoops.
- Shell : BusyBox ash répond aux commandes via `/dev/cu.usbmodem1101`. Le marqueur `SHELL_PROOF_b3aa1217bdb3a052` est une sortie de commande et n’apparaît pas littéralement dans l’entrée envoyée.
- Preuves : `logs/stage1-validation.json`, `logs/ram-validated.json`, `logs/last-boot-images.json`, `logs/usb-shell.log`.

Le dongle est laissé sous Linux. Pour ouvrir la console sur ce Mac :

```sh
screen /dev/cu.usbmodem1101 115200
```

Une coupure USB perd ce Linux en RAM et ramène en FEL, puisque boot0 est effacé. Pour reproduire, exécuter `ddr-awboot`, `test-ram`, puis `boot` dans cet ordre. Lancer `python3 stage1/tools/usb-shell-check.py` avant `boot` pour attendre un nouveau port ACM et capturer automatiquement la preuve du shell. Le nom du port peut changer.

Le test mémoire recharge le watchdog par Mio et l’arrête lui-même avant de rendre FEL. L’hôte attend jusqu’à 120 secondes la commande USB suivante. Le lancement Linux arme un watchdog de 16 secondes ; `/init` l’arrête après configuration du gadget USB par l’hôte. Cette récupération requiert boot0 effacé. Ramoops s’enregistre correctement, mais la conservation de son contenu après reset n’a pas été éprouvée.

Ce résultat valide le démarrage Linux en RAM et la console USB. Wi-Fi, vidéo, audio et les fonctions applicatives du dongle n’ont pas été testés. MTD/SPI/MMC sont désactivés ; aucune écriture flash n’a été faite pendant ces essais RAM.
