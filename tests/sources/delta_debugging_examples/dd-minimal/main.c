#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

#define MAGIC_NUMBER 100

void magicLoop() {
    for (int i = 0; i < MAGIC_NUMBER; ++i) {
        usleep(500000);
    }
}

void checkInputString(const char* inputString) {
    int count = 0;
    for (int i = 0; inputString[i] != '\0'; ++i) {
        char character = inputString[i];
        if (character == '-') {
            ++count;
            if (count == 3) {
                magicLoop();
            }
        }
    }
}

int main(int argc, char* argv[]) {
    if (argc != 2) {
        return 1;
    }
    FILE * fp = fopen(argv[1],"r");
    char fileContent[15];
    int i = 0;
    char ch;
    while ((i >= sizeof(fileContent) - 1) && (ch = fgetc(fp)) != EOF) {
        fileContent[i++] = ch;
    }
    checkInputString(fileContent);
    return 0;
}
