function showError(errorMessage) {
    Swal.fire({
//      title: errorMessage,
      text: getErrorMessageText(errorMessage),
      icon: "error"
    });
  }

  function getErrorMessageText(errorType) {
    switch(errorType) {
      case 'No selected file':
        return "Необходимо добавить файл";
      case 'Not allowed type':
        return "Недопустимый формат файла";
      case 'Incorrect shape':
        return "Некорректный размер изображения";
      case 'Modality_error':
        return "Модальность в DICOM не соответствует целевой модальности сервиса";
      case 'Series_error':
        return "Нет подходящих для обработки серий в исследовании";
      case 'Body_part_error':
        return "На изображении не распознан целевой орган";
      case 'Images_error':
        return "Сервис не смог определить, что изображено в DICOM-файле";
      case 'Other':
        return "Другая ошибка, требующая информации от ИИ-сервиса, в том числе ошибки заполнения тегов";
      case 'Server_unavailable':
        return "Ошибка загрузки DICOM: отсутствует связь или сервер не отвечает";
      case 'Incorrect_number_of_images':
        return "Полученное количество изображений отличается от ожидаемого";
      default:
        return "";
    }
  }


