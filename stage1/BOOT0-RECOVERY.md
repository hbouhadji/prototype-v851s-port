# Boot0 sauvegardé puis effacé le 24 septembre 2026

L’utilisateur a demandé l’effacement de boot0 pour entrer en FEL à chaque démarrage. Sa table MTD identifie boot0 comme une partition de 1 Mio, suivie de 3 Mio d’U-Boot, 1 Mio de secure_storage et 123 Mio de sys. Elle est conservée dans `logs/proc-mtd-user-20260924.txt`.

La NAND est détectée par xfel comme `GD5F1GQ4UExIG`, capacité 134 217 728 octets. La lecture de NAND utilise la SRAM et fonctionne sans initialisation DDR. Le premier Mio et les 3 Mio suivants ont été sauvegardés via FEL et comparés octet par octet au dump complet existant : correspondance exacte.

Sauvegarde boot0 : `out/boot0-fel-backup-20260924.bin`, 1 048 576 octets.

SHA-256 : `62f10f397bda47111e2d0df5c1887c7bf9155d76ca71ff890767e2774afe8f0d`.

La seule commande destructive exécutée était :

```sh
stage1/tools/xfel spinand erase 0 1048576
```

La relecture des 4 premiers Mio confirme que le premier Mio vaut entièrement `0xff` et qu’U-Boot est inchangé. Aucune commande d’écriture/effacement n’a ciblé les partitions suivantes. Les preuves sont dans `logs/boot0-erase-manifest.json`, les journaux associés et `out/boot0-and-uboot-after-erase-20260924.bin`.

Après `xfel reset`, `xfel version` répond de nouveau en FEL. Le retour en FEL a également été confirmé après le débranchement/rebranchement physique signalé par l’utilisateur le 25 septembre 2026. Le bootloader d’origine est conservé en sauvegarde ; il n’est plus présent sur la NAND.

## Restauration à effectuer seulement lorsqu’elle est souhaitée

La programmation/restauration n’a pas encore été testée sur ce dongle. La commande `spinand write` de cette version de xfel efface les blocs couvrant le fichier puis programme les données. La procédure ci-dessous cible exactement la sauvegarde de 1 Mio ; elle ne doit pas recevoir le dump complet par inadvertance.

Depuis la racine du projet, vérifier d’abord la taille et le SHA-256 indiqués ci-dessus. Puis, pour restaurer le démarrage d’origine :

```sh
stage1/tools/xfel spinand write 0 stage1/out/boot0-fel-backup-20260924.bin
stage1/tools/xfel spinand read 0 1048576 stage1/out/boot0-restored-readback.bin
cmp stage1/out/boot0-fel-backup-20260924.bin stage1/out/boot0-restored-readback.bin
```

Ne redémarrer qu’après une comparaison réussie ; contrôler ensuite le démarrage réel du firmware. Le dump complet `firmware-128MiB.bin` contient également les mêmes octets de boot0.
