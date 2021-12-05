import { Component } from '@angular/core';
import {NgxFileDropEntry} from "ngx-file-drop";
import {HttpClient} from "@angular/common/http";

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {

  constructor(private http: HttpClient) {}

  public files: NgxFileDropEntry[] = [];
  file: Blob | undefined = undefined;
  tempUrl: any = undefined;

  public dropped(files: NgxFileDropEntry[]) {
    this.files = files;
    console.log(this.files);
    for (const droppedFile of files) {
      const fileEntry = droppedFile.fileEntry as FileSystemFileEntry;
      fileEntry.file((file: File) => {

        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = (_event) => {
          this.tempUrl = reader.result;
        }

        this.file = file;
      });
    }
  }

  runInference() {
    const formData = new FormData();
    formData.append('req_image', this.file as Blob);

    this.http.post('http://localhost:8080/inference', formData, {
      responseType: 'json'
    }).subscribe(data => {
      console.log(data);
    });
  }
}
