# Faisabilité du stage 1 V851S

> Cette étude initiale est conservée comme historique. Les essais ultérieurs, le dump complet de 128 Mio et l’effacement demandé de boot0 sont documentés dans [stage1/README.md](../stage1/README.md) et [BOOT0-RECOVERY.md](../stage1/BOOT0-RECOVERY.md).

Étude du 24 septembre 2026, à partir de l’issue [catplay-firmware #18](https://github.com/catplay-labs/catplay-firmware/issues/18), des sources publiques et du fichier local `firmware-16MiB.bin`.

**Avis : stage 1 techniquement crédible, mais pas directement compilable et utilisable avec les configurations proposées par défaut.** Les principales inconnues sont l’identité exacte de la carte, son initialisation DRAM et la transition FEL → gadget USB. Aucun démarrage ni transfert vers le matériel n’a été réalisé dans cette étude ; aucun firmware n’a été compilé.

Le critère de réussite demandé est un démarrage par FEL d’un Linux minimal fournissant un shell via `g_serial`, ou via CDC-NCM et telnet/SSH. Le port complet CatPlay, les codecs vidéo, le Wi-Fi, le stockage et U-Boot complet ne sont pas nécessaires à ce jalon. La réussite de ce jalon ne prouverait pas celle d’un dongle de transcodage complet.

## Constats sur les sources

### Linux a déjà démarré sur V851S

Le [retour de test de septembre 2023](https://github.com/szemzoa/awboot/issues/23#issuecomment-1722536266) fournit un patch Linux 6.6-rc1 et un journal de démarrage Yuzuki Lizard. Le dépôt awboot contient aussi un [journal Linux 6.11.5](https://github.com/szemzoa/awboot/blob/5380c00fc67c975433f25c57fb481aa2b91aebf8/linux-6.11-v851s.txt) : Cortex-A7, 64 Mio, démarrage du système et fonctionnement d’un périphérique Wi-Fi USB en mode hôte. Cela prouve une base Linux utilisable sur cette famille, mais pas le mode gadget après FEL sur le dongle étudié.

Comparaison des trois bases citées dans l’issue :

| Base | Éléments vérifiés | Conséquence |
| --- | --- | --- |
| Patch joint 6.6-rc1 | 17 fichiers modifiés ; DT USB avec un compatible PHY V851S, mais aucune modification du pilote PHY dans cette pièce jointe | Boot Linux attesté ; pièce jointe insuffisante à elle seule pour conclure au support USB. L’auteur mentionne une correction USB ultérieure dans les commentaires. |
| `linux/linux-6.13-rc1-wip.patch` d’awboot | 51 fichiers ; CCU, pinctrl, DT, ajout du compatible et de la configuration PHY V853 ; contrôleur MUSB compatible A33 | Bon candidat pour un premier prototype autonome, en désactivant les périphériques hors périmètre. Pas de preuve du passage FEL → gadget. |
| Série LKML v2, février 2025 | Cible 6.14-rc1, 10 patches, corrections d’horloges, PHY, DT ; dépendance explicite à une autre série pinctrl | Base plus propre pour la suite ; il faut résoudre cette dépendance avant de la choisir comme chemin le plus rapide. |

Source de la série v2 : [présentation LKML](https://lkml.iu.edu/hypermail/linux/kernel/2502.0/04878.html). Son contenu couvre la famille V853/V851S/V851S3 ; il ne faut pas confondre soumission sur LKML et intégration effective à une version du noyau.

**Choix proposé : prototype sur 6.13-rc1 avec son patch WIP**, après vérification d’application et compilation. Garder 6.6 comme référence et la série v2 comme source de corrections. Un rebase immédiat vers la version 7.2 évoquée par l’issue ajoute du travail qui ne valide pas le matériel. Cette étude n’a pas effectué ces compilations ni audité le support dans un noyau récent.

### awboot nécessite une adaptation réelle

Révision examinée : `5380c00fc67c975433f25c57fb481aa2b91aebf8`.

- [`arch/arch.mk`](https://github.com/szemzoa/awboot/blob/5380c00fc67c975433f25c57fb481aa2b91aebf8/arch/arch.mk) sélectionne `mach-t113s3`. Le Makefile compile `board.c` et référence aussi le linker T113 pour FEL. Le fichier `board-v851s.c` ne suffit pas à sélectionner une cible fonctionnelle.
- [`tools/fel.sh`](https://github.com/szemzoa/awboot/blob/5380c00fc67c975433f25c57fb481aa2b91aebf8/tools/fel.sh) appelle `xfel ddr t113-s3`, suppose 128 Mio et utilise GNU `stat -c`. Il doit être adapté au matériel et à macOS, ou exécuté dans un environnement Linux pour les parties appropriées.
- Le code V851S prévoit DDR2 à 528 MHz. Ce n’est pas la configuration trouvée dans le dump local.
- Le démarrage courant passe par des fonctions PSCI/non-secure ajoutées au chemin T113. Plusieurs fichiers correspondants ne sont pas présents dans `mach-v851s` : remplacer simplement le chemin SoC ne constitue pas un port.
- `main.c` réinitialise la DRAM avant de lire les images téléversées. Pour un parcours en deux étapes, initialiser la DRAM, revenir à FEL, charger les images, puis préserver cette DRAM lors du lancement. Les tests mémoire et la réinitialisation après chargement peuvent détruire les données.
- Le watchdog est réglé à trois secondes avant l’entrée noyau : à traiter explicitement pour éviter des redémarrages trompeurs.

Le V851S démarre Linux sur **ARM Cortex-A7**. Le passage au noyau suit donc `r0=0`, `r1=~0` pour DT, `r2=adresse du DTB`, avec l’état CPU approprié, MMU et cache de données désactivés. La référence à `a0/a1/a2` dans l’issue ne doit pas être reprise littéralement ; ces noms correspondent au contexte RISC-V du V821. Référence : [protocole officiel de démarrage ARM Linux](https://docs.kernel.org/arch/arm/booting.html).

### FEL et USB

[`xfel/chips/v851_v853.c`](https://github.com/xboot/xfel/blob/445e8aefe6914c85817cc9bd1d201629364b0ec6/chips/v851_v853.c) reconnaît l’identifiant `0x00188600`. Il contient une charge d’initialisation DDR et deux jeux de paramètres. Le profil `v851` est DDR2 ; le profil `v853` est DDR3 mais ne correspond pas exactement au boot0 local. La bonne approche est un profil explicite issu du dump, puis des lectures/écritures mémoire vérifiées. La concordance des paramètres n’est pas à elle seule une preuve d’équivalence complète de la séquence d’initialisation.

Le port V821 de CatPlay contient des adaptations MUSB/PHY, horloges, resets et changement de rôle. Elles constituent une référence de méthode, pas des patches à copier sans vérifier les registres V85x. La [documentation V821](https://github.com/catplay-labs/catplay-firmware/blob/bd33f3286a7bac6b2569d331441332ccf3201f54/docs/V821.md) montre une transition FEL → gadget réussie sur cet autre SoC.

Pour le premier essai : DT minimal avec USB en `peripheral`, contrôleurs hôtes désactivés, pile gadget intégrée au noyau et `g_serial` en mode ACM, BusyBox statique et shell sur `ttyGS0`. Passer à CDC-NCM après la première énumération stable. La remise à zéro de MUSB/PHY et l’état VBUS restent à valider sur la carte.

## Analyse du dump local

- Taille : 16 777 216 octets.
- SHA-256 : `c832ec38f4a46dce16a261e430369b52986729254ced1c3e0d9850b4027b457a`.
- Huit copies identiques de boot0, à `0x0`, `0x20000`, …, `0xe0000`.
- Chaque copie fait 45 056 octets et son checksum eGON recalculé vaut bien `0x53ff799d`.
- Deux DTB distincts décodables, chacun présent trois fois : première occurrence à `0x1c6c34` (19 082 octets) et `0x1ccc00` (102 912 octets). Les extractions et leur décompilation figurent à côté de cette note.
- Compatible : `allwinner,v851`, `arm,sun8iw21p1` ; CPU Cortex-A7.
- Le grand DTB active SPI-NAND et désactive le nœud SPI-NOR ; des en-têtes UBI sont présents à partir de `0x500000`, dont des checksums EC vérifiés.

Le bloc DRAM du boot0 commence à `0x38`. Il indique `dram_clk=936`, `dram_type=3` (DDR3), `dram_para1=0x10d2`, `dram_para2=0x00800000`. Selon la convention observée dans le pilote awboot, ce dernier champ est cohérent avec **128 Mio** ; c’est un indice de variante V851S3, à confirmer par le matériel et un test mémoire. La taille de flash et la taille de RAM sont indépendantes.

Le DTB déclare pourtant une fenêtre mémoire de 512 Mio et des paramètres DRAM différents : vraisemblablement des valeurs génériques ajustées au démarrage. Ne pas les utiliser comme preuve de la RAM réellement installée. Les paramètres détaillés extraits du boot0 sont conservés dans `boot0-dram.json`.

**Le fichier de 16 Mio n’est pas encore une sauvegarde complète vérifiée.** La présence de NAND/UBI, la redondance des bootloaders et le partitionnement déclaré ne correspondent pas à l’hypothèse simple d’une petite flash NOR de 16 Mio. En interprétant les offsets de partitions comme des secteurs de 512 octets, la dernière partition commence vers 68,5 Mio. Certaines positions des en-têtes UBI ne correspondent pas non plus directement aux offsets annoncés par les en-têtes EC : la méthode d’extraction et la géométrie doivent être clarifiées avant toute reconstruction/restauration. Un DTB peut être générique ; ces indices ne suffisent pas à déterminer la capacité physique exacte.

Il faut relever `/proc/mtd`, les tailles/types MTD et la commande de sauvegarde, puis confirmer la correspondance avec ce dongle. L’effacement de `mtdblock0` proposé dans l’issue n’est pas un prérequis pour étudier le port ou tenter un démarrage RAM si une entrée FEL réversible est disponible. Il ne devrait pas être le premier essai avec cette sauvegarde non validée.

## Jalons et charge estimative

| Jalon | Preuve attendue | Estimation indicative |
| --- | --- | --- |
| Identifier carte, flash, sauvegarde et accès FEL | Identifiant SoC, tailles réelles, sauvegarde vérifiée, méthode de retour FEL | 0,5–1 jour |
| DRAM adaptée au boot0 | Écritures/lectures répétées sur plusieurs zones et vérification de la capacité sans alias | 1–2 jours |
| Trampoline ARM et Linux minimal | Log noyau/init obtenu ; images préservées et plan mémoire vérifié | 1–3 jours |
| Reprise USB et shell | Déconnexion FEL puis énumération ACM ; commandes shell exécutées | 1–4 jours |

Ordre de grandeur : **environ une à deux semaines de travail** si la carte est accessible et instrumentable. Ce n’est pas un engagement de délai. Une DRAM instable, l’absence de console ou un blocage PHY peut ajouter plusieurs semaines. Le développement assisté par IA aide à produire les variantes ; il ne remplace pas les observations matérielles.

Une console UART serait très utile : le DTB local pointe vers UART0 à `0x02500000`, tandis que la carte Lizard d’awboot utilise UART2 à `0x02500800`. Le brochage et la tension doivent être identifiés pour cette carte. Sans UART, prévoir des marqueurs d’étape en SRAM récupérables via FEL lorsque possible ; une disparition USB seule ne prouve pas que Linux a démarré.

Le livrable stage 1 doit réunir les sources et versions épinglées, la configuration noyau, le DTS spécifique, l’initramfs, le chargeur FEL, les adresses et tailles vérifiées, ainsi qu’un journal démontrant plusieurs redémarrages à froid et un shell fonctionnel. Aucun driver vidéo ni image Yocto complète n’est nécessaire pour cette validation.

**Décision conseillée : lancer un prototype RAM, après identification du dump et validation de la DRAM.** Les sources disponibles suffisent à justifier cette exploration. Elles ne permettent pas encore de promettre le fonctionnement USB sur ce dongle précis ni d’estimer sérieusement le port complet CatPlay.
